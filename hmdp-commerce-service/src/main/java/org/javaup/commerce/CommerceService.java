package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;

/**
 * 商城读码入口3：普通交易状态机。先读createOrder，再读pay/closeInside，最后读redeem。
 * 不使用本类自调用的@Transactional：所有关键写入都显式进入同一CommerceDatabase.tx。
 * 模拟支付没有外部扣款副作用，故可以将付款、库存售出、凭证放在一个MySQL事务里； 真实渠道扣款不能套用此原子性结论，需要回调、退款和对账。
 */
@Service
public class CommerceService {
  @org.springframework.beans.factory.annotation.Autowired CoreDirectoryClient directory;
  final CommerceDatabase db;
  final CommerceAccess access;
  final SnowflakeIdGenerator ids;

  @Value("${commerce.mock-payment-enabled:false}")
  boolean mockEnabled;

  @Value("${commerce.payment-minutes:15}")
  int paymentMinutes;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceService(CommerceDatabase db, CommerceAccess access, SnowflakeIdGenerator ids) {
    this.db = db;
    this.access = access;
    this.ids = ids;
  }

  Map<String, Object> one(String sql, Object... args) {
    var rows = db.repo.queryForList(sql, args);
    require(!rows.isEmpty(), 404, "记录不存在");
    return rows.get(0);
  }

  static long number(Object value) {
    try {
      return Long.parseLong(String.valueOf(value));
    } catch (Exception e) {
      throw new CommerceProblem(400, "编号格式不正确");
    }
  }

  static String text(Object value) {
    return value == null ? "" : value.toString().trim();
  }

  static String required(Map<String, Object> form, String key, int max) {
    String value = text(form.get(key));
    require(!value.isEmpty() && value.length() <= max, 400, key + "格式不正确");
    return value;
  }

  static String key(Map<String, Object> form) {
    String k = required(form, "requestKey", 80);
    require(k.matches("[A-Za-z0-9_-]{8,80}"), 400, "请求编号格式不正确");
    return k;
  }

  static LocalDateTime date(Object v) {
    // 新版MySQL驱动对DATETIME通常返回LocalDateTime，不能假定始终为旧JDBC Timestamp。
    if (v instanceof LocalDateTime time) return time;
    if (v instanceof java.sql.Timestamp stamp) return stamp.toLocalDateTime();
    throw new IllegalStateException(
        "不支持的数据库时间类型: " + (v == null ? "null" : v.getClass().getName()));
  }

  static String quote(Map<String, Object> row) {
    return row.get("product_version") + "-" + row.get("version");
  }

  static BigDecimal price(Object v) {
    try {
      BigDecimal p = new BigDecimal(text(v));
      require(
          p.signum() > 0 && p.scale() <= 2 && p.compareTo(new BigDecimal("99999999.99")) <= 0,
          400,
          "价格须为正数，最多两位小数");
      return p.setScale(2);
    } catch (NumberFormatException e) {
      throw new CommerceProblem(400, "价格格式不正确");
    }
  }

  public Map<String, Object> products(String q, String category, int page, String sort) {
    require(page > 0 && page <= 10000, 400, "页码不正确");
    require(q.length() <= 100, 400, "搜索词过长");
    String where =
        " WHERE p.status='ACTIVE' AND (?='' OR p.title LIKE ?) AND (?='' OR p.category=?)";
    Object[] filter = {q, "%" + q + "%", category, category};
    long total =
        db.repo.queryForObject("SELECT COUNT(*) FROM mall_product p" + where, Long.class, filter);
    String order =
        // 稳定交错展示不同题材，不是个性化推荐；先取模避免19位ID乘法溢出。
        "explore".equals(sort)
            ? "MOD(MOD(p.id,101)*37,101),p.id DESC"
            : "price".equals(sort)
                ? "min_price,p.id DESC"
                : "price_desc".equals(sort) ? "min_price DESC,p.id DESC" : "p.id DESC";
    List<Object> args = new ArrayList<>(Arrays.asList(filter));
    args.add((page - 1) * 12);
    var rows =
        db.repo.queryForList(
            "SELECT p.*,(SELECT MIN(k.price) FROM mall_sku k WHERE"
                + " k.product_id=p.id) min_price,(SELECT COALESCE(SUM(k.available),0) FROM mall_sku"
                + " k WHERE k.product_id=p.id) available FROM mall_product p"
                + where
                + " ORDER BY "
                + order
                + " LIMIT 12 OFFSET ?",
            args.toArray());
    var metadata=directory.shops(rows.stream().map(row->number(row.get("shop_id"))).distinct().toList());
    rows.forEach(row->row.put("shop_name",metadata.getOrDefault(number(row.get("shop_id")),Map.of()).getOrDefault("name","门店信息暂缺")));
    return Map.of("list", rows, "total", total, "page", page);
  }

  public Map<String, Object> product(long id) {
    var p =
        one(
            "SELECT * FROM mall_product WHERE id=?",
            id);
    var shop=directory.shop(number(p.get("shop_id")));
    p.put("shop_name",shop.getOrDefault("name","门店信息暂缺"));p.put("address",shop.getOrDefault("address",""));
    require("ACTIVE".equals(p.get("status")), 404, "商品已下架");
    p.put(
        "skus",
        db.repo.queryForList(
            "SELECT k.*,a.id activity_id,a.starts_at,a.ends_at,a.status activity_status FROM"
                + " mall_sku k LEFT JOIN mall_seckill_activity a ON a.sku_id=k.id WHERE"
                + " k.product_id=? ORDER BY k.id",
            id));
    return p;
  }

  Map<String, Object> sku(long id, boolean lock) {
    // 统一锁顺序：商品→SKU。避免后台改价与下单按相反顺序锁行。
    long pid = number(one("SELECT product_id FROM mall_sku WHERE id=?", id).get("product_id"));
    if (lock) one("SELECT id FROM mall_product WHERE id=? FOR UPDATE", pid);
    var row = one("SELECT * FROM mall_sku WHERE id=?" + (lock ? " FOR UPDATE" : ""), id);
    var product =
        one(
            "SELECT title,cover,rules,status,shop_id,version product_version FROM mall_product WHERE id=?",
            pid);
    product.put("shop_name",directory.shop(number(product.get("shop_id"))).getOrDefault("name","门店信息暂缺"));
    row.putAll(product);
    return row;
  }

  public Map<String, Object> quoteFor(long id) {
    var s = sku(id, false);
    require("ACTIVE".equals(s.get("status")), 409, "商品已下架");
    s.put("quoteVersion", quote(s));
    return s;
  }

  Map<String, Object> existing(long uid, String key) {
    var rows =
        db.repo.queryForList(
            "SELECT * FROM mall_trade_order WHERE user_id=? AND request_key=?", uid, key);
    return rows.isEmpty() ? null : rows.get(0);
  }

  Map<String, Object> replay(Map<String, Object> old, long sku, String version) {
    require(
        number(old.get("sku_id")) == sku && version.equals(old.get("quote_version")),
        409,
        "同一请求编号不能更换购买参数");
    return old;
  }

  public Map<String, Object> createOrder(Map<String, Object> form) {
    long uid = access.user(), sid = number(form.get("skuId"));
    String request = key(form), version = required(form, "quoteVersion", 64);
    require(!request.startsWith("sk-"), 400, "请求编号使用了系统保留前缀");
    try {
      return db.tx.execute(
          tx -> {
            var old = existing(uid, request);
            if (old != null) return replay(old, sid, version);
            var s = sku(sid, true);
            // 在锁内再次检查，处理同SKU并发重试；跨SKU同键由数据库唯一键兜底，失败事务回滚库存。
            old = existing(uid, request);
            if (old != null) return replay(old, sid, version);
            require("ACTIVE".equals(s.get("status")), 409, "商品已下架");
            require("NORMAL".equals(s.get("sale_mode")), 409, "该规格请从秒杀活动购买");
            require(version.equals(quote(s)), 409, "商品价格或规则已变化，请重新确认报价");
            require(
                db.repo.skus.update(null, new com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper<org.javaup.commerce.persistence.SkuEntity>()
                        .eq("id",sid).gt("available",0).setSql("available=available-1,reserved=reserved+1"))
                    == 1,
                409,
                "该规格已售罄");
            long id = ids.nextId();
            LocalDateTime now = LocalDateTime.now();
            return insertOrder(
                id, uid, s, request, now, now.plusMinutes(paymentMinutes), "普通购买，库存已预占");
          });
    } catch (DuplicateKeyException e) {
      var old = existing(uid, request);
      if (old != null) return replay(old, sid, version);
      throw e;
    }
  }

  /** 普通购买和RabbitMQ消费共用快照落单，调用者必须先处于同库事务并成功预占MySQL库存。 */
  Map<String, Object> insertOrder(
      long id,
      long uid,
      Map<String, Object> s,
      String request,
      LocalDateTime created,
      LocalDateTime expires,
      String detail) {
    long sid = number(s.get("id"));
    var order = new org.javaup.commerce.persistence.TradeOrderEntity();
    order.id=id; order.userId=uid; order.shopId=number(s.get("shop_id")); order.skuId=sid;
    order.title=text(s.get("title"));order.skuName=text(s.get("name"));order.cover=text(s.get("cover"));
    order.shopName=text(s.get("shop_name"));order.rules=text(s.get("rules"));order.validDays=(int)number(s.get("valid_days"));
    order.amount=price(s.get("price"));order.status="WAIT_PAY";order.requestKey=request;order.quoteVersion=quote(s);
    order.createdAt=created;order.expiresAt=expires;db.repo.orders.insert(order);
    movement(sid, id, "RESERVE", -1, uid);
    event(id, uid, "CREATE", detail);
    return orderRow(id, false);
  }

  Map<String, Object> orderRow(long id, boolean lock) {
    return one("SELECT * FROM mall_trade_order WHERE id=?" + (lock ? " FOR UPDATE" : ""), id);
  }

  void owner(Map<String, Object> order) {
    require(number(order.get("user_id")) == access.user(), 403, "无权操作该订单");
  }

  Map<String, Object> decorated(Map<String, Object> order) {
    long id = number(order.get("id"));
    order.put(
        "events",
        db.repo.queryForList(
            "SELECT event_type,detail,created_at FROM mall_order_event WHERE order_id=? ORDER BY"
                + " id",
            id));
    var tickets = db.repo.queryForList("SELECT * FROM mall_redemption WHERE order_id=?", id);
    if (!tickets.isEmpty()) order.put("redemption", tickets.get(0));
    order.put("serverTime", LocalDateTime.now().toString());
    order.put("mockPaymentEnabled", mockEnabled);
    return order;
  }

  public Map<String, Object> order(long id) {
    return db.tx.execute(
        tx -> {
          var order = orderRow(id, true);
          owner(order);
          expireInside(order);
          return decorated(orderRow(id, false));
        });
  }

  public Map<String, Object> orders(int page, String status) {
    long uid = access.user();
    require(page > 0 && page < 10000, 400, "页码不正确");
    var pending =
        db.repo.queryForList(
            "SELECT id FROM mall_trade_order WHERE user_id=? AND status IN ('WAIT_PAY','PAID')"
                + " ORDER BY id LIMIT 100",
            uid);
    for (var row : pending) expire(number(row.get("id")));
    Object[] args = {uid, status, status};
    return Map.of(
        "list",
        db.repo.queryForList(
            "SELECT * FROM mall_trade_order WHERE user_id=? AND (?='' OR status=?) ORDER BY id DESC"
                + " LIMIT 12 OFFSET ?",
            uid,
            status,
            status,
            (page - 1) * 12),
        "total",
        db.repo.queryForObject(
            "SELECT COUNT(*) FROM mall_trade_order WHERE user_id=? AND (?='' OR status=?)",
            Long.class,
            args));
  }

  public Map<String, Object> pay(long id, Map<String, Object> form) {
    require(mockEnabled, 404, "此环境未开启模拟支付");
    long uid = access.user();
    String request = key(form), outcome = required(form, "outcome", 16);
    require(Set.of("SUCCESS", "FAILED").contains(outcome), 400, "请选择模拟成功或失败");
    return db.tx.execute(
        tx -> {
          var order = orderRow(id, true);
          owner(order);
          var attempts =
              db.repo.queryForList(
                  "SELECT * FROM mall_payment_attempt WHERE user_id=? AND request_key=?",
                  uid,
                  request);
          if (!attempts.isEmpty()) {
            var attempt = attempts.get(0);
            require(
                number(attempt.get("order_id")) == id && outcome.equals(attempt.get("outcome")),
                409,
                "付款请求编号已用于其他操作");
            var result = decorated(order);
            result.put("attemptOutcome", attempt.get("outcome"));
            return result;
          }
          expireInside(order);
          order = orderRow(id, false);
          if (Set.of("PAID", "USED", "EXPIRED").contains(text(order.get("status"))))
            return decorated(order);
          // 过期关闭需要提交；不能关单后抛异常导致刚才的关闭一起回滚。
          if ("CLOSED".equals(order.get("status"))) return decorated(order);
          LocalDateTime now = LocalDateTime.now();
          if ("FAILED".equals(outcome)) {
            payment(id, uid, request, outcome, order.get("amount"), now);
            event(id, uid, "PAY_FAILED", "模拟支付失败，期限内可重新尝试");
          } else {
            // 行锁只串行化当前订单；SQL仍带旧状态与期限，避免未来调用路径绕过检查。
            require(
                db.repo.update(
                        "UPDATE mall_trade_order SET status='PAID',paid_at=? WHERE id=? AND"
                            + " user_id=? AND status='WAIT_PAY' AND expires_at>?",
                        now,
                        id,
                        uid,
                        now)
                    == 1,
                409,
                "订单状态或支付期限已变化");
            require(
                db.repo.update(
                        "UPDATE mall_sku SET reserved=reserved-1,sold=sold+1 WHERE id=? AND"
                            + " reserved>0",
                        order.get("sku_id"))
                    == 1,
                409,
                "库存预占异常，请联系管理员");
            payment(id, uid, request, outcome, order.get("amount"), now);
            db.repo.update(
                "INSERT INTO mall_redemption(id,order_id,shop_id,code,status,expires_at)"
                    + " VALUES(?,?,?,?,'READY',?)",
                ids.nextId(),
                id,
                order.get("shop_id"),
                UUID.randomUUID().toString().replace("-", ""),
                now.plusDays(number(order.get("valid_days"))));
            movement(number(order.get("sku_id")), id, "SELL", 0, uid);
            event(id, uid, "PAID", "模拟支付成功，电子凭证已生成");
          }
          var result = decorated(orderRow(id, false));
          result.put("attemptOutcome", outcome);
          return result;
        });
  }

  void payment(
      long id, long uid, String request, String outcome, Object amount, LocalDateTime now) {
    db.repo.update(
        "INSERT INTO"
            + " mall_payment_attempt(id,order_id,user_id,request_key,outcome,amount,created_at)"
            + " VALUES(?,?,?,?,?,?,?)",
        ids.nextId(),
        id,
        uid,
        request,
        outcome,
        amount,
        now);
  }

  public Map<String, Object> cancel(long id) {
    return db.tx.execute(
        tx -> {
          var o = orderRow(id, true);
          owner(o);
          if ("WAIT_PAY".equals(o.get("status"))) closeInside(o, "USER_CANCEL");
          else require("CLOSED".equals(o.get("status")), 409, "只有待支付订单可以取消");
          return decorated(orderRow(id, false));
        });
  }

  /** 只有成功抢到旧状态的调用才释放预占；本地事务失败会连同状态一起回滚。 */
  void closeInside(Map<String, Object> o, String reason) {
    long id = number(o.get("id"));
    if (db.repo.update(
            "UPDATE mall_trade_order SET status='CLOSED',closed_at=?,close_reason=? WHERE id=? AND"
                + " status='WAIT_PAY'",
            LocalDateTime.now(),
            reason,
            id)
        == 0) return;
    require(
        db.repo.update(
                "UPDATE mall_sku SET reserved=reserved-1,available=available+1 WHERE id=? AND"
                    + " reserved>0",
                o.get("sku_id"))
            == 1,
        409,
        "库存预占异常，关闭已回滚");
    movement(number(o.get("sku_id")), id, "RELEASE", 1, number(o.get("user_id")));
    event(id, number(o.get("user_id")), "CLOSED", reason);
    // 与订单关闭同事务记录待回补终态。Redis故障不能丢掉修复依据，后台按此结果重复同步。
    db.repo.update(
        "UPDATE mall_seckill_result SET status='CLOSED',sync_pending=1 WHERE reservation_id=? AND"
            + " status='CREATED'",
        id);
    db.repo.update("DELETE FROM mall_seckill_limit WHERE reservation_id=?", id);
  }

  void expireInside(Map<String, Object> o) {
    LocalDateTime now = LocalDateTime.now();
    long id = number(o.get("id"));
    if ("WAIT_PAY".equals(o.get("status")) && !date(o.get("expires_at")).isAfter(now))
      closeInside(o, "PAYMENT_TIMEOUT");
    if ("PAID".equals(o.get("status"))) {
      var ticket = one("SELECT * FROM mall_redemption WHERE order_id=?", id);
      if (!date(ticket.get("expires_at")).isAfter(now)) {
        db.repo.update(
            "UPDATE mall_trade_order SET status='EXPIRED' WHERE id=? AND status='PAID'", id);
        db.repo.update(
            "UPDATE mall_redemption SET status='EXPIRED' WHERE order_id=? AND status='READY'", id);
        event(id, null, "EXPIRED", "使用期限已过，不回补已售库存");
      }
    }
  }

  void expire(long id) {
    db.tx.executeWithoutResult(tx -> expireInside(orderRow(id, true)));
  }

  public void expireBatch() {
    var due =
        db.repo.queryForList(
            "SELECT id FROM mall_trade_order WHERE status='WAIT_PAY' AND expires_at<=? ORDER BY"
                + " expires_at LIMIT 100",
            LocalDateTime.now());
    for (var row : due) expire(number(row.get("id")));
    var tickets =
        db.repo.queryForList(
            "SELECT order_id id FROM mall_redemption WHERE status='READY' AND expires_at<=? LIMIT"
                + " 100",
            LocalDateTime.now());
    for (var row : tickets) expire(number(row.get("id")));
  }

  public Map<String, Object> redemption(String code, boolean confirm) {
    require(code != null && code.matches("[a-f0-9]{32}"), 400, "请输入完整的32位凭证码");
    // 所有入口先锁订单再锁凭证，避免核销与凭证过期的锁顺序相反。
    var lookup = one("SELECT order_id,shop_id FROM mall_redemption WHERE code=?", code);
    access.shop(number(lookup.get("shop_id")));
    return db.tx.execute(
        tx -> {
          long id = number(lookup.get("order_id"));
          var o = orderRow(id, true);
          expireInside(o);
          o = orderRow(id, false);
          var ticket = one("SELECT * FROM mall_redemption WHERE order_id=? FOR UPDATE", id);
          if (confirm) {
            if (!"USED".equals(o.get("status"))) {
              require(
                  "PAID".equals(o.get("status")) && "READY".equals(ticket.get("status")),
                  409,
                  "凭证当前不可核销");
              LocalDateTime now = LocalDateTime.now();
              require(
                  db.repo.update(
                          "UPDATE mall_redemption SET status='USED',used_at=?,used_by=? WHERE"
                              + " order_id=? AND status='READY' AND expires_at>?",
                          now,
                          access.user(),
                          id,
                          now)
                      == 1,
                  409,
                  "凭证已使用或过期");
              require(
                  db.repo.update(
                          "UPDATE mall_trade_order SET status='USED',used_at=? WHERE id=? AND"
                              + " status='PAID'",
                          now,
                          id)
                      == 1,
                  409,
                  "订单状态已变化");
              event(id, access.user(), "USED", "所属门店完成整份套餐核销");
            }
          }
          // 工作台只返回业务必需信息，不返回买家身份和原始请求键。
          var result = new LinkedHashMap<String, Object>();
          o = orderRow(id, false);
          for (String field :
              List.of("id", "title", "sku_name", "shop_name", "amount", "status", "used_at"))
            result.put(field, o.get(field));
          result.put("expires_at", ticket.get("expires_at"));
          return result;
        });
  }

  void movement(long sku, long order, String action, int delta, Long actor) {
    db.repo.update(
        "INSERT INTO mall_stock_movement(id,sku_id,order_id,action,delta,actor_id)"
            + " VALUES(?,?,?,?,?,?)",
        ids.nextId(),
        sku,
        order,
        action,
        delta,
        actor);
  }

  void event(long id, Long actor, String event, String detail) {
    db.repo.update(
        "INSERT INTO mall_order_event(id,order_id,actor_id,event_type,detail) VALUES(?,?,?,?,?)",
        ids.nextId(),
        id,
        actor,
        event,
        detail);
  }

  public List<Map<String, Object>> merchantProducts(long shop) {
    access.shop(shop);
    var rows =
        db.repo.queryForList("SELECT * FROM mall_product WHERE shop_id=? ORDER BY id DESC", shop);
    for (var row : rows)
      row.put(
          "skus",
          db.repo.queryForList(
              "SELECT k.*,a.id activity_id,a.status activity_status FROM mall_sku k LEFT JOIN"
                  + " mall_seckill_activity a ON a.sku_id=k.id WHERE k.product_id=? ORDER BY k.id",
              row.get("id")));
    return rows;
  }

  public List<Map<String, Object>> merchantOrders(long shop, int page) {
    access.shop(shop);
    require(page > 0 && page <= 10000, 400, "页码不正确");
    return db.repo.queryForList(
        "SELECT id,title,sku_name,amount,status,created_at,paid_at,used_at FROM mall_trade_order"
            + " WHERE shop_id=? ORDER BY id DESC LIMIT 12 OFFSET ?",
        shop,
        (page - 1) * 12);
  }

  public Map<String, Object> saveProduct(Map<String, Object> form) {
    long shop = number(form.get("shopId"));
    access.shop(shop);
    require(!directory.shop(shop).isEmpty(),404,"门店不存在");
    String title = required(form, "title", 100),
        category = required(form, "category", 20),
        description = required(form, "description", 4000),
        rules = required(form, "rules", 2000),
        cover = required(form, "cover", 255),
        status = required(form, "status", 16);
    require(Set.of("运动", "手作", "文娱", "休闲").contains(category), 400, "分类不正确");
    require(Set.of("DRAFT", "ACTIVE", "OFFLINE").contains(status), 400, "商品状态不正确");
    require(
        cover.matches("/imgs/(commerce/[a-z-]+\\.svg|blogs/upload/[a-zA-Z0-9/_.-]+)"),
        400,
        "请选择已上传图片或场景插画");
    String name = required(form, "skuName", 60);
    BigDecimal price = price(form.get("price"));
    long days = number(form.get("validDays"));
    require(days >= 1 && days <= 365, 400, "有效期须为1至365天");
    return db.tx.execute(
        tx -> {
          if (form.get("id") == null) {
            long rawStock = number(form.get("stock"));
            require(rawStock >= 0 && rawStock <= 100000, 400, "库存范围不正确");
            int stock = (int) rawStock;
            long id = ids.nextId(), sid = ids.nextId();
            var p = new org.javaup.commerce.persistence.ProductEntity();
            p.id=id; p.shopId=shop; p.title=title; p.category=category; p.cover=cover;
            p.description=description; p.rules=rules; p.status=status;
            db.repo.products.insert(p);
            var sku = new org.javaup.commerce.persistence.SkuEntity();
            sku.id=sid; sku.productId=id; sku.name=name; sku.price=price;
            sku.available=stock; sku.validDays=(int)days;
            db.repo.skus.insert(sku);
            return Map.of("id", id, "skuId", sid);
          }
          long id = number(form.get("id"));
          var product = one("SELECT * FROM mall_product WHERE id=? FOR UPDATE", id);
          require(number(product.get("shop_id")) == shop, 403, "商品不属于该门店");
          require(
              db.repo.queryForObject(
                      "SELECT COUNT(*) FROM mall_seckill_activity a JOIN mall_sku k ON"
                          + " k.id=a.sku_id WHERE k.product_id=? AND a.status IN"
                          + " ('ACTIVE','STOPPING')",
                      Integer.class,
                      id)
                  == 0,
              409,
              "商品有进行中或待开始活动，配置已冻结");
          require(number(product.get("version")) == number(form.get("version")), 409, "商品已被修改，请刷新");
          var skus =
              db.repo.queryForList(
                  "SELECT * FROM mall_sku WHERE product_id=? ORDER BY id FOR UPDATE", id);
          require(!skus.isEmpty(), 409, "商品没有规格");
          long sid =
              form.get("skuId") == null ? number(skus.get(0).get("id")) : number(form.get("skuId"));
          var selected =
              skus.stream()
                  .filter(s -> number(s.get("id")) == sid)
                  .findFirst()
                  .orElseThrow(() -> new CommerceProblem(403, "规格不属于该商品"));
          require("NORMAL".equals(selected.get("sale_mode")), 409, "活动规格请停止活动后再修改");
          db.repo.update(
              "UPDATE mall_product SET"
                  + " title=?,category=?,cover=?,description=?,rules=?,status=?,version=version+1"
                  + " WHERE id=?",
              title,
              category,
              cover,
              description,
              rules,
              status,
              id);
          db.repo.update(
              "UPDATE mall_sku SET name=?,price=?,valid_days=?,version=version+1 WHERE id=?",
              name,
              price,
              days,
              sid);
          return Map.of("id", id, "skuId", sid);
        });
  }

  public Map<String, Object> stock(long sid, Map<String, Object> form) {
    long delta = number(form.get("delta"));
    require(delta != 0 && Math.abs(delta) <= 100000, 400, "调整数量不正确");
    return db.tx.execute(
        tx -> {
          var s = sku(sid, true);
          access.shop(number(s.get("shop_id")));
          require("NORMAL".equals(s.get("sale_mode")), 409, "活动库存不可直接调整");
          long version = number(form.get("version"));
          require(version == number(s.get("version")), 409, "规格已变更，请刷新");
          require(
              db.repo.update(
                      "UPDATE mall_sku SET available=available+?,version=version+1 WHERE id=? AND"
                          + " available+?>=0",
                      delta,
                      sid,
                      delta)
                  == 1,
              409,
              "可售库存不足");
          movement(sid, version, "ADJUST", (int) delta, access.user());
          return sku(sid, false);
        });
  }
}
