package org.javaup.commerce;

import static org.junit.jupiter.api.Assertions.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.IntStream;
import org.javaup.dto.UserDTO;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.javaup.utils.UserHolder;
import org.junit.jupiter.api.*;

/** 真实MySQL事务测试，不启动Spring全应用、不连接演示Redis、不改演示业务schema。 删除夹具前验证实际DATABASE，避免把“隔离”只写在注释里。 */
class CommerceServiceIntegrationTest {
  static CommerceDatabase db;
  CommerceService service;
  CommerceAccess access;

  @BeforeAll
  static void database() {
    db =
        new CommerceDatabase(
            "jdbc:mysql://mysql:3306/hmdp_commerce_test?serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false",
            "hmdp",
            "plus-local");
  }

  @AfterAll
  static void close() {
    db.close();
  }

  static void as(long id) {
    UserDTO u = new UserDTO();
    u.setId(id);
    UserHolder.saveUser(u);
  }

  @BeforeEach
  void seed() {
    assertEquals("hmdp_commerce_test", db.repo.queryForObject("SELECT DATABASE()", String.class));
    for (String t :
        List.of(
            "mall_seckill_limit",
            "mall_seckill_result",
            "mall_seckill_activity",
            "mall_redemption",
            "mall_payment_attempt",
            "mall_order_event",
            "mall_stock_movement",
            "mall_trade_order",
            "mall_sku",
            "mall_product",
            "mall_shop_member")) db.repo.update("DELETE FROM " + t);
    db.repo.execute(
        "CREATE TABLE IF NOT EXISTS tb_shop(id BIGINT PRIMARY KEY,name VARCHAR(100),address"
            + " VARCHAR(200))");
    db.repo.update(
        "INSERT IGNORE INTO tb_shop(id,name,address)"
            + " VALUES(1,'测试门店甲','隔离数据库'),(2,'测试门店乙','隔离数据库')");
    db.repo.update(
        "INSERT INTO mall_product(id,shop_id,title,category,cover,description,rules,status)"
            + " VALUES(1,1,'测试体验','运动','/imgs/commerce/sport.svg','体验内容','下单规则','ACTIVE'),(2,2,'其他门店','运动','/imgs/commerce/sport.svg','内容','规则','ACTIVE')");
    db.repo.update(
        "INSERT INTO mall_sku(id,product_id,name,price,available,valid_days)"
            + " VALUES(1,1,'单人',19.90,20,30),(2,1,'双人',29.90,20,30),(3,2,'其他门店套餐',9.90,20,30)");
    db.repo.update(
        "INSERT INTO mall_shop_member VALUES(20,1,'MERCHANT'),(21,2,'MERCHANT'),(30,0,'ADMIN')");
    access = new CommerceAccess(db);
    service = new CommerceService(db, access, new SnowflakeIdGenerator(31, 31));
    service.directory = new CoreDirectoryClient(){
      @Override public Map<String,Object> shop(long id){return Map.of("id",id,"name","事务测试门店","address","");}
    };
    service.mockEnabled = true;
    service.paymentMinutes = 15;
    as(10);
  }

  @AfterEach
  void clearThread() {
    UserHolder.removeUser();
  }

  Map<String, Object> create(String request) {
    return service.createOrder(Map.of("skuId", "1", "quoteVersion", "1-1", "requestKey", request));
  }

  long orderId(String request) {
    return CommerceService.number(create(request).get("id"));
  }

  Map<String, Object> pay(long id, String key) {
    return service.pay(id, Map.of("requestKey", key, "outcome", "SUCCESS"));
  }

  long scalar(String sql, Object... args) {
    return db.repo.queryForObject(sql, Long.class, args);
  }

  void problem(int status, Runnable fn) {
    var e = assertThrows(CommerceProblem.class, fn::run);
    assertEquals(status, e.status);
  }

  <T> List<T> concurrent(int n, java.util.function.IntFunction<T> action) throws Exception {
    ExecutorService pool = Executors.newFixedThreadPool(n);
    CountDownLatch start = new CountDownLatch(1);
    try {
      List<Future<T>> futures =
          IntStream.range(0, n)
              .mapToObj(
                  i ->
                      pool.submit(
                          () -> {
                            start.await();
                            as(10);
                            try {
                              return action.apply(i);
                            } finally {
                              UserHolder.removeUser();
                            }
                          }))
              .toList();
      start.countDown();
      List<T> results = new ArrayList<>();
      for (var f : futures) results.add(f.get(20, TimeUnit.SECONDS));
      return results;
    } finally {
      pool.shutdownNow();
    }
  }

  @Test
  void quoteSnapshotsAndMoney() {
    assertEquals(new BigDecimal("19.90"), service.quoteFor(1).get("price"));
    problem(
        409,
        () ->
            service.createOrder(
                Map.of("skuId", "1", "quoteVersion", "stale", "requestKey", "quote-stale-key")));
    long id = orderId("snapshot-key");
    db.repo.update("UPDATE mall_sku SET price=99.99,valid_days=1,version=version+1 WHERE id=1");
    db.repo.update(
        "UPDATE mall_product SET title='新名称',rules='新规则',status='OFFLINE',version=version+1 WHERE"
            + " id=1");
    var paid = pay(id, "snapshot-payment");
    assertEquals("测试体验", paid.get("title"));
    assertEquals(new BigDecimal("19.90"), paid.get("amount"));
    var ticket = service.one("SELECT * FROM mall_redemption WHERE order_id=?", id);
    assertTrue(
        CommerceService.date(ticket.get("expires_at")).isAfter(LocalDateTime.now().plusDays(29)));
  }

  @Test
  void concurrentSubmitOnlyReservesOnce() throws Exception {
    var results = concurrent(8, i -> create("same-submit-key"));
    assertEquals(1, results.stream().map(r -> r.get("id")).distinct().count());
    assertEquals(19, scalar("SELECT available FROM mall_sku WHERE id=1"));
    assertEquals(1, scalar("SELECT COUNT(*) FROM mall_trade_order"));
    problem(
        409,
        () ->
            service.createOrder(
                Map.of("skuId", "2", "quoteVersion", "1-1", "requestKey", "same-submit-key")));
  }

  @Test
  void lastStockHasOneWinner() throws Exception {
    db.repo.update("UPDATE mall_sku SET available=1 WHERE id=1");
    var results =
        concurrent(
            8,
            i -> {
              try {
                create("last-stock-key-" + i);
                return true;
              } catch (CommerceProblem p) {
                assertEquals(409, p.status);
                return false;
              }
            });
    assertEquals(1, results.stream().filter(Boolean::booleanValue).count());
    assertEquals(0, scalar("SELECT available FROM mall_sku WHERE id=1"));
  }

  @Test
  void paymentRetriesIssueOneTicket() throws Exception {
    long id = orderId("payment-order-key");
    service.pay(id, Map.of("requestKey", "failed-attempt-key", "outcome", "FAILED"));
    assertEquals("WAIT_PAY", service.order(id).get("status"));
    concurrent(8, i -> pay(id, "successful-attempt-key"));
    assertEquals(1, scalar("SELECT COUNT(*) FROM mall_redemption WHERE order_id=?", id));
    assertEquals(1, scalar("SELECT sold FROM mall_sku WHERE id=1"));
    assertEquals(0, scalar("SELECT reserved FROM mall_sku WHERE id=1"));
    assertEquals(2, scalar("SELECT COUNT(*) FROM mall_payment_attempt"));
    problem(
        409,
        () -> service.pay(id, Map.of("requestKey", "failed-attempt-key", "outcome", "SUCCESS")));
  }

  @Test
  void paymentAndCancellationCompete() throws Exception {
    long id = orderId("race-order-key");
    concurrent(
        10,
        i -> {
          try {
            return i % 2 == 0 ? pay(id, "race-pay-key") : service.cancel(id);
          } catch (CommerceProblem p) {
            assertEquals(409, p.status);
            return Map.of();
          }
        });
    String status = service.order(id).get("status").toString();
    assertTrue(Set.of("PAID", "CLOSED").contains(status));
    assertEquals(0, scalar("SELECT reserved FROM mall_sku WHERE id=1"));
    assertEquals(20, scalar("SELECT available+sold FROM mall_sku WHERE id=1"));
    assertEquals("PAID".equals(status) ? 1 : 0, scalar("SELECT COUNT(*) FROM mall_redemption"));
    assertTrue(scalar("SELECT COUNT(*) FROM mall_stock_movement WHERE action='RELEASE'") <= 1);
  }

  @Test
  void overduePaymentClosesWithoutScheduler() {
    long id = orderId("overdue-order-key");
    db.repo.update(
        "UPDATE mall_trade_order SET expires_at=? WHERE id=?",
        LocalDateTime.now().minusSeconds(1),
        id);
    assertEquals("CLOSED", pay(id, "overdue-payment-key").get("status"));
    service.expireBatch();
    service.cancel(id);
    assertEquals(20, scalar("SELECT available FROM mall_sku WHERE id=1"));
    assertEquals(1, scalar("SELECT COUNT(*) FROM mall_stock_movement WHERE action='RELEASE'"));
    assertEquals(0, scalar("SELECT COUNT(*) FROM mall_payment_attempt"));
  }

  @Test
  void unauthorizedUserAndOtherShopCannotOperate() {
    long id = orderId("owner-order-key");
    as(11);
    problem(403, () -> service.order(id));
    problem(403, () -> pay(id, "other-pay-key"));
    problem(403, () -> service.cancel(id));
    as(10);
    pay(id, "owner-payment-key");
    String code =
        service.one("SELECT code FROM mall_redemption WHERE order_id=?", id).get("code").toString();
    as(21);
    problem(403, () -> service.redemption(code, true));
    as(10);
    problem(403, () -> access.shop(1));
    as(20);
    assertEquals("USED", service.redemption(code, true).get("status"));
    assertEquals("USED", service.redemption(code, true).get("status"));
    assertEquals(1, scalar("SELECT COUNT(*) FROM mall_order_event WHERE event_type='USED'"));
  }

  @Test
  void concurrentRedemptionOnlyOnce() throws Exception {
    long id = orderId("redeem-order-key");
    pay(id, "redeem-payment-key");
    String code =
        service.one("SELECT code FROM mall_redemption WHERE order_id=?", id).get("code").toString();
    concurrent(
        8,
        i -> {
          as(20);
          return service.redemption(code, true);
        });
    assertEquals(1, scalar("SELECT COUNT(*) FROM mall_order_event WHERE event_type='USED'"));
  }

  @Test
  void failureAfterPaymentStateRollsBackEverything() {
    long id = orderId("rollback-order-key");
    // 用测试表CHECK注入真实写入失败，无需生产用户SUPER权限或改变MySQL全局安全配置。
    db.repo.execute(
        "ALTER TABLE mall_redemption ADD CONSTRAINT test_fail_ticket CHECK (order_id < 0)");
    try {
      assertThrows(Exception.class, () -> pay(id, "rollback-payment-key"));
    } finally {
      db.repo.execute("ALTER TABLE mall_redemption DROP CHECK test_fail_ticket");
    }
    assertEquals("WAIT_PAY", service.order(id).get("status"));
    assertEquals(1, scalar("SELECT reserved FROM mall_sku WHERE id=1"));
    assertEquals(0, scalar("SELECT sold FROM mall_sku WHERE id=1"));
    assertEquals(0, scalar("SELECT COUNT(*) FROM mall_payment_attempt"));
    assertEquals(0, scalar("SELECT COUNT(*) FROM mall_redemption"));
    assertEquals("PAID", pay(id, "rollback-payment-key").get("status"));
  }

  @Test
  void expiredPaidTicketDoesNotRestock() {
    long id = orderId("expired-ticket-order");
    pay(id, "expired-ticket-payment");
    db.repo.update(
        "UPDATE mall_redemption SET expires_at=? WHERE order_id=?",
        LocalDateTime.now().minusSeconds(1),
        id);
    service.expireBatch();
    assertEquals("EXPIRED", service.order(id).get("status"));
    assertEquals(1, scalar("SELECT sold FROM mall_sku WHERE id=1"));
    assertEquals(19, scalar("SELECT available FROM mall_sku WHERE id=1"));
  }

  @Test
  void mockMustBeEnabled() {
    long id = orderId("disabled-order-key");
    service.mockEnabled = false;
    problem(404, () -> pay(id, "disabled-payment-key"));
    assertEquals("WAIT_PAY", service.order(id).get("status"));
  }

  @Test
  void stockAdjustmentUsesVersionGuard() {
    as(20);
    service.stock(1, Map.of("delta", -2, "version", 1));
    problem(409, () -> service.stock(1, Map.of("delta", -2, "version", 1)));
    assertEquals(18, scalar("SELECT available FROM mall_sku WHERE id=1"));
    as(21);
    problem(403, () -> service.stock(1, Map.of("delta", 1, "version", 2)));
  }
}
