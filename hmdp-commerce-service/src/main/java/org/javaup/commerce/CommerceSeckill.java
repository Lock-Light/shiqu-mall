package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;
import static org.javaup.commerce.CommerceService.*;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import com.rabbitmq.client.Channel;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** 商城读码入口4：Lua预占→持久待投递索引→RabbitMQ→MySQL终态→幂等Redis同步。 MySQL结果表同时是同步待办(outbox)。没有把Redis与MySQL宣称成一个事务。 */
@Service
public class CommerceSeckill {
  final CommerceService commerce;
  final CommerceDatabase db;
  final CommerceAccess access;
  final StringRedisTemplate redis;
  final CommerceMessaging messaging;
  final ObjectMapper json = new ObjectMapper();
  final DefaultRedisScript<List> reserve = new DefaultRedisScript<>();
  final DefaultRedisScript<Long> sync = new DefaultRedisScript<>();
  final DefaultRedisScript<Long> claim =
      new DefaultRedisScript<>(
          "local s=redis.call('ZSCORE',KEYS[1],ARGV[1]);if s and tonumber(s)<=tonumber(ARGV[2])"
              + " then redis.call('ZADD',KEYS[1],ARGV[3],ARGV[1]);return 1 end;return 0",
          Long.class);
  final DefaultRedisScript<Long> reschedule =
      new DefaultRedisScript<>(
          "return redis.call('ZADD',KEYS[1],'XX',ARGV[2],ARGV[1])", Long.class);
  long activityCursor = 0;

  @Value("${prefix.distinction.name:hmdp}")
  String prefix;

  @Value("${commerce.dispatch-enabled:true}")
  boolean dispatchEnabled;

  @Value("${commerce.sync-enabled:true}")
  boolean syncEnabled;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceSeckill(
      CommerceService commerce,
      CommerceDatabase db,
      CommerceAccess access,
      StringRedisTemplate redis,
      CommerceMessaging messaging) {
    this.commerce = commerce;
    this.db = db;
    this.access = access;
    this.redis = redis;
    this.messaging = messaging;
    reserve.setLocation(new ClassPathResource("lua/commerceReserve.lua"));
    reserve.setResultType(List.class);
    sync.setLocation(new ClassPathResource("lua/commerceSync.lua"));
    sync.setResultType(Long.class);
  }

  List<String> keys(long aid, long uid) {
    String base = prefix + ":mall:{" + aid + "}:";
    return List.of(
        base + "stock",
        base + "buyers",
        base + "payloads",
        base + "states",
        base + "pending",
        base + "rate:" + uid,
        base + "open");
  }

  String encode(Object value) {
    try {
      return json.writeValueAsString(value);
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  Map<String, Object> decode(String value) {
    try {
      return json.readValue(value, new TypeReference<Map<String, Object>>() {});
    } catch (Exception e) {
      throw new IllegalStateException("秒杀消息协议不正确", e);
    }
  }

  Map<String, Object> activity(long id) {
    return commerce.one(
        "SELECT a.*,k.product_id,p.shop_id FROM mall_seckill_activity a JOIN mall_sku k ON"
            + " k.id=a.sku_id JOIN mall_product p ON p.id=k.product_id WHERE a.id=?",
        id);
  }

  static long millis(LocalDateTime date) {
    return date.atZone(ZoneId.of("Asia/Shanghai")).toInstant().toEpochMilli();
  }

  public Map<String, Object> publish(Map<String, Object> form) {
    long sid = number(form.get("skuId"));
    LocalDateTime begin, end;
    try {
      begin = LocalDateTime.parse(required(form, "startsAt", 40));
      end = LocalDateTime.parse(required(form, "endsAt", 40));
    } catch (Exception e) {
      throw new CommerceProblem(400, "活动时间格式不正确");
    }
    require(
        end.isAfter(begin)
            && end.isAfter(LocalDateTime.now())
            && Duration.between(begin, end).toDays() <= 30,
        400,
        "活动时间范围不正确");
    var a =
        db.tx.execute(
            tx -> {
              var s = commerce.sku(sid, true);
              access.shop(number(s.get("shop_id")));
              var existing =
                  db.repo.queryForList("SELECT * FROM mall_seckill_activity WHERE sku_id=?", sid);
              if (!existing.isEmpty()) {
                require(
                    date(existing.get(0).get("starts_at")).equals(begin)
                        && date(existing.get(0).get("ends_at")).equals(end),
                    409,
                    "该规格已有活动，不能重置活动库存");
                return existing.get(0);
              }
              require(
                  "ACTIVE".equals(s.get("status")) && "NORMAL".equals(s.get("sale_mode")),
                  409,
                  "只有在售普通规格可以建立专属活动");
              require(
                  number(s.get("reserved")) == 0
                      && number(s.get("sold")) == 0
                      && number(s.get("available")) > 0
                      && number(s.get("available")) <= 1000,
                  409,
                  "请选择未发生交易且库存为1至1000的独立规格");
              long aid = commerce.ids.nextId();
              db.repo.update(
                  "UPDATE mall_sku SET sale_mode='SECKILL',version=version+1 WHERE id=?", sid);
              db.repo.update(
                  "INSERT INTO"
                      + " mall_seckill_activity(id,sku_id,starts_at,ends_at,status,initial_stock)"
                      + " VALUES(?,?,?,?,'CONFIGURING',?)",
                  aid,
                  sid,
                  begin,
                  end,
                  s.get("available"));
              return activity(aid);
            });
    if ("CONFIGURING".equals(a.get("status"))) {
      // 只在尚未开放的活动初始化；ACTIVE库存缺失绝不从初始数量自动重置。
      redis
          .opsForValue()
          .setIfAbsent(keys(number(a.get("id")), 0).get(0), text(a.get("initial_stock")));
      redis.opsForValue().set(keys(number(a.get("id")), 0).get(6), "ACTIVE");
      db.repo.update(
          "UPDATE mall_seckill_activity SET status='ACTIVE' WHERE id=? AND status='CONFIGURING'",
          a.get("id"));
    }
    return activity(number(a.get("id")));
  }

  /** 先关Redis入口再记STOPPING，允许已经受理的单完成或超时；不强行清资格/返库存。 */
  public Map<String, Object> stop(long aid) {
    var a = activity(aid);
    access.shop(number(a.get("shop_id")));
    redis.opsForValue().set(keys(aid, 0).get(6), "CLOSED");
    db.repo.update(
        "UPDATE mall_seckill_activity SET status='STOPPING' WHERE id=? AND status IN"
            + " ('ACTIVE','CONFIGURING')",
        aid);
    finishStopped();
    return activity(aid);
  }

  void finishStopped() {
    for (var a :
        db.repo.queryForList(
            "SELECT a.id FROM mall_seckill_activity a JOIN mall_sku k ON k.id=a.sku_id WHERE"
                + " a.status='STOPPING' AND k.reserved=0 ORDER BY a.id LIMIT 100")) {
      Long pending = redis.opsForZSet().zCard(keys(number(a.get("id")), 0).get(4));
      if (Long.valueOf(0).equals(pending))
        db.repo.update(
            "UPDATE mall_seckill_activity SET status='CLOSED' WHERE id=? AND status='STOPPING'",
            a.get("id"));
    }
  }

  public Map<String, Object> reserve(long aid, Map<String, Object> form) {
    long uid = access.user();
    String request = key(form);
    var a = activity(aid);
    require("ACTIVE".equals(a.get("status")), 409, "活动未开放");
    var s = commerce.sku(number(a.get("sku_id")), false);
    require("ACTIVE".equals(s.get("status")), 409, "商品已下架");
    long rid = commerce.ids.nextId();
    LocalDateTime now = LocalDateTime.now();
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("reservationId", String.valueOf(rid));
    payload.put("activityId", String.valueOf(aid));
    payload.put("userId", String.valueOf(uid));
    payload.put("skuId", text(a.get("sku_id")));
    payload.put("requestKey", request);
    payload.put("createdAt", now.toString());
    payload.put("expiresAt", now.plusMinutes(commerce.paymentMinutes).toString());
    List<?> result =
        redis.execute(
            reserve,
            keys(aid, uid),
            String.valueOf(uid),
            String.valueOf(rid),
            encode(payload),
            String.valueOf(millis(date(a.get("starts_at")))),
            String.valueOf(millis(date(a.get("ends_at")))));
    require(result != null && !result.isEmpty(), 503, "活动暂不可用，请查询已有结果");
    long code = number(result.get(0));
    require(code >= 0, 409, text(result.get(1)));
    return Map.of(
        "reservationId",
        text(result.get(1)),
        "activityId",
        String.valueOf(aid),
        "status",
        "QUEUED",
        "message",
        "资格已受理，需查询数据库落单结果");
  }

  Map<String, Object> payload(long aid, long rid) {
    Object raw = redis.opsForHash().get(keys(aid, 0).get(2), String.valueOf(rid));
    require(raw != null, 404, "预占记录不存在，请勿重复提交");
    return decode(raw.toString());
  }

  public Map<String, Object> result(long aid, long rid) {
    long uid = access.user();
    var rows =
        db.repo.queryForList("SELECT * FROM mall_seckill_result WHERE reservation_id=?", rid);
    if (!rows.isEmpty()) {
      var row = rows.get(0);
      require(
          number(row.get("user_id")) == uid && number(row.get("activity_id")) == aid,
          403,
          "无权查询该抢购结果");
      Map<String, Object> result = new LinkedHashMap<>(row);
      if ("CREATED".equals(row.get("status")) || "CLOSED".equals(row.get("status")))
        result.put("orderId", String.valueOf(rid));
      return result;
    }
    var body = payload(aid, rid);
    require(
        number(body.get("userId")) == uid && number(body.get("activityId")) == aid, 403, "无权查询该预占");
    return Map.of("status", "QUEUED", "reservationId", String.valueOf(rid));
  }

  @RabbitListener(queues="${commerce.rabbit.queue:commerce-orders-v2}",containerFactory="commerceRabbitFactory")
  public void consume(String message, Channel channel,@Header(AmqpHeaders.DELIVERY_TAG) long tag) throws java.io.IOException {
    var envelope = decode(message);
    long aid = number(envelope.get("activityId")), rid = number(envelope.get("reservationId"));
    // RabbitMQ只携带指针；资格主体从Redis原子账本读取，不能信任一条消息自行指定金额/用户。
    var body = payload(aid, rid);
    settle(aid, rid, body, false);
    channel.basicAck(tag,false); // Only after the MySQL transaction commits.
  }

  void settle(long aid, long rid, Map<String, Object> body, boolean rejectExpired) {
    long uid = number(body.get("userId"));
    db.tx.executeWithoutResult(
        tx -> {
          db.repo.update(
              "INSERT IGNORE INTO mall_seckill_result(reservation_id,activity_id,user_id,status)"
                  + " VALUES(?,?,?,'PROCESSING')",
              rid,
              aid,
              uid);
          var result =
              commerce.one(
                  "SELECT * FROM mall_seckill_result WHERE reservation_id=? FOR UPDATE", rid);
          require(
              number(result.get("activity_id")) == aid && number(result.get("user_id")) == uid,
              409,
              "预占主体不匹配");
          if (!"PROCESSING".equals(result.get("status"))) {
            db.repo.update(
                "UPDATE mall_seckill_result SET sync_pending=1 WHERE reservation_id=?", rid);
            return;
          }
          LocalDateTime created = LocalDateTime.parse(text(body.get("createdAt"))),
              expires = LocalDateTime.parse(text(body.get("expiresAt")));
          if (rejectExpired || !expires.isAfter(LocalDateTime.now())) {
            reject(rid, "预占已过付款期限");
            return;
          }
          var a = activity(aid);
          require(number(a.get("sku_id")) == number(body.get("skuId")), 409, "活动规格不匹配");
          var s = commerce.sku(number(body.get("skuId")), true);
          // 资格基于进入Lua的时间；活动结束后、付款期限内已获资格仍可完成落单。
          if (!"ACTIVE".equals(s.get("status"))
              || created.isBefore(date(a.get("starts_at")))
              || !created.isBefore(date(a.get("ends_at")))) {
            reject(rid, "活动或商品已失效");
            return;
          }
          var limit =
              db.repo.queryForList(
                  "SELECT reservation_id FROM mall_seckill_limit WHERE activity_id=? AND user_id=?"
                      + " FOR UPDATE",
                  aid,
                  uid);
          if (!limit.isEmpty() && number(limit.get(0).get("reservation_id")) != rid) {
            reject(rid, "该用户已有有效活动订单");
            return;
          }
          db.repo.update(
              "INSERT IGNORE INTO mall_seckill_limit(activity_id,user_id,reservation_id)"
                  + " VALUES(?,?,?)",
              aid,
              uid,
              rid);
          if (db.repo.update(
                  "UPDATE mall_sku SET available=available-1,reserved=reserved+1 WHERE id=? AND"
                      + " available>0",
                  s.get("id"))
              != 1) {
            db.repo.update("DELETE FROM mall_seckill_limit WHERE reservation_id=?", rid);
            reject(rid, "数据库库存不足");
            return;
          }
          commerce.insertOrder(rid, uid, s, "sk-" + rid, created, expires, "限量抢购经RabbitMQ实际落单，库存已预占");
          db.repo.update(
              "UPDATE mall_seckill_result SET status='CREATED',sync_pending=1 WHERE"
                  + " reservation_id=?",
              rid);
        });
  }

  void reject(long rid, String reason) {
    db.repo.update(
        "UPDATE mall_seckill_result SET status='REJECTED',reason=?,sync_pending=1 WHERE"
            + " reservation_id=?",
        reason,
        rid);
  }

  /** 投递租约只减少并行投递，不能保证恰好一次；数据库终态负责抵御重复消息。 */
  @Scheduled(fixedDelay = 1000, initialDelay = 5000)
  public void dispatch() {
    if (!dispatchEnabled) return;
    try {
      var batch =
          db.repo.queryForList(
              "SELECT id FROM mall_seckill_activity WHERE id>? ORDER BY id LIMIT 100",
              activityCursor);
      if (batch.isEmpty()) {
        activityCursor = 0;
        return;
      }
      for (var a : batch) {
        activityCursor = number(a.get("id"));
        long aid = number(a.get("id"));
        var keys = keys(aid, 0);
        long now = System.currentTimeMillis();
        var due = redis.opsForZSet().rangeByScore(keys.get(4), 0, now, 0, 20);
        if (due == null) continue;
        for (String id : due) {
          if (!Long.valueOf(1)
              .equals(
                  redis.execute(
                      claim,
                      List.of(keys.get(4)),
                      id,
                      String.valueOf(now),
                      String.valueOf(now + 5000)))) continue;
          var body = payload(aid, number(id));
          if (!LocalDateTime.parse(text(body.get("expiresAt"))).isAfter(LocalDateTime.now())) {
            settle(aid, number(id), body, true);
            continue;
          }
          messaging.send(id,encode(Map.of("reservationId",id,"activityId",String.valueOf(aid))));
          // 不因Broker确认而删除待办。消费者未提交/同步前，10秒后允许再次投递。
          redis.execute(
              reschedule,
              List.of(keys.get(4)),
              id,
              String.valueOf(System.currentTimeMillis() + 10000));
        }
      }
    } catch (Exception e) {
      LoggerFactory.getLogger(getClass()).warn("商城预占投递暂未完成，保留账本重试: {}", e.toString());
    }
  }

  @Scheduled(fixedDelay = 1000, initialDelay = 5000)
  public void synchronize() {
    if (!syncEnabled) return;
    try {
      finishStopped();
      for (var pending :
          db.repo.queryForList(
              "SELECT reservation_id FROM mall_seckill_result WHERE sync_pending=1 ORDER BY"
                  + " reservation_id LIMIT 100")) {
        db.tx.executeWithoutResult(
            tx -> {
              var row =
                  commerce.one(
                      "SELECT * FROM mall_seckill_result WHERE reservation_id=? FOR UPDATE",
                      pending.get("reservation_id"));
              if (number(row.get("sync_pending")) != 1) return;
              long aid = number(row.get("activity_id")), rid = number(row.get("reservation_id"));
              String state = text(row.get("status"));
              if (!Set.of("CREATED", "CLOSED", "REJECTED").contains(state)) return;
              Long done =
                  redis.execute(
                      sync,
                      keys(aid, 0).subList(0, 5),
                      String.valueOf(rid),
                      text(row.get("user_id")),
                      state);
              // Redis记录丢失必须人工对账，不能重新SET初始库存掩盖问题。
              require(Long.valueOf(1).equals(done), 503, "Redis预占账本缺失，保留数据库待办");
              db.repo.update(
                  "UPDATE mall_seckill_result SET sync_pending=0 WHERE reservation_id=?", rid);
            });
      }
    } catch (Exception e) {
      LoggerFactory.getLogger(getClass()).warn("商城库存同步待重试: {}", e.toString());
    }
  }
}
