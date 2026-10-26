package org.javaup.commerce;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.*;
import org.javaup.dto.Result;
import org.springframework.web.bind.annotation.*;

@RestController
public class CommerceController {
  final CommerceService service;
  final CommerceAccess access;
  final CommerceThrottle throttle;
  final CommerceContent content;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceController(
      CommerceService service,
      CommerceAccess access,
      CommerceThrottle throttle,
      CommerceContent content) {
    this.service = service;
    this.access = access;
    this.throttle = throttle;
    this.content = content;
  }

  /** ID始终字符串，金额为两位小数元字符串；避免前端精度损失和旧券单位混淆。 */
  static Object view(Object value) {
    if (value instanceof Map<?, ?> map) {
      Map<String, Object> out = new LinkedHashMap<>();
      map.forEach((k, v) -> out.put(k.toString(), view(v)));
      return out;
    }
    if (value instanceof List<?> list) return list.stream().map(CommerceController::view).toList();
    // 金额列本身为DECIMAL(10,2)；坐标也使用BigDecimal，不能把所有小数强制当成两位金额。
    if (value instanceof BigDecimal decimal) return decimal.toPlainString();
    if (value instanceof Long) return value.toString();
    if (value instanceof Timestamp stamp) return stamp.toLocalDateTime().toString();
    return value;
  }

  Result<?> ok(Object value) {
    return Result.ok(view(value));
  }

  @GetMapping("/mall/products")
  public Result<?> products(
      @RequestParam(defaultValue = "") String q,
      @RequestParam(defaultValue = "") String category,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(defaultValue = "") String sort) {
    return ok(service.products(q, category, page, sort));
  }

  @GetMapping("/mall/products/{id}")
  public Result<?> product(@PathVariable long id) {
    return ok(content.decorate(service.product(id)));
  }

  @GetMapping("/mall/shops/{id}")
  public Result<?> shopProfile(@PathVariable long id) {
    return ok(content.shop(id));
  }

  @GetMapping("/mall/places")
  public Result<?> places(
      @RequestParam(defaultValue = "") String q,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(defaultValue = "121.474") double x,
      @RequestParam(defaultValue = "31.230") double y) {
    return ok(content.places(q, page, x, y));
  }

  @GetMapping("/mall/stories")
  public Result<?> stories(@RequestParam(defaultValue = "1") int page) {
    return ok(content.stories(page));
  }

  @GetMapping("/mall/skus/{id}/quote")
  public Result<?> quote(@PathVariable long id) {
    return ok(service.quoteFor(id));
  }

  @GetMapping("/mall/me")
  public Result<?> me() {
    return ok(
        Map.of(
            "userId", access.user(), "memberships", access.memberships(), "admin", access.admin()));
  }

  @PostMapping("/trade/orders")
  public Result<?> create(@RequestBody Map<String, Object> form) {
    return ok(service.createOrder(form));
  }

  @GetMapping("/trade/orders")
  public Result<?> orders(
      @RequestParam(defaultValue = "1") int page, @RequestParam(defaultValue = "") String status) {
    return ok(service.orders(page, status));
  }

  @GetMapping("/trade/orders/{id}")
  public Result<?> order(@PathVariable long id) {
    return ok(service.order(id));
  }

  @GetMapping("/trade/orders/{id}/redemption")
  public Result<?> ticket(@PathVariable long id) {
    return ok(service.order(id).get("redemption"));
  }

  @PostMapping("/trade/orders/{id}/mock-pay")
  public Result<?> pay(@PathVariable long id, @RequestBody Map<String, Object> form) {
    return ok(service.pay(id, form));
  }

  @PostMapping("/trade/orders/{id}/cancel")
  public Result<?> cancel(@PathVariable long id) {
    return ok(service.cancel(id));
  }

  @GetMapping("/merchant/products")
  public Result<?> merchantProducts(@RequestParam long shopId) {
    return ok(service.merchantProducts(shopId));
  }

  @PostMapping("/merchant/products")
  public Result<?> save(@RequestBody Map<String, Object> form) {
    return ok(service.saveProduct(form));
  }

  @PostMapping("/merchant/skus/{id}/stock")
  public Result<?> stock(@PathVariable long id, @RequestBody Map<String, Object> form) {
    return ok(service.stock(id, form));
  }

  @GetMapping("/merchant/orders")
  public Result<?> merchantOrders(
      @RequestParam long shopId, @RequestParam(defaultValue = "1") int page) {
    return ok(service.merchantOrders(shopId, page));
  }

  @PostMapping("/merchant/redemptions/preview")
  public Result<?> preview(@RequestBody Map<String, Object> form) {
    throttle.check("preview");
    return ok(service.redemption(CommerceService.text(form.get("code")), false));
  }

  @PostMapping("/merchant/redemptions/confirm")
  public Result<?> confirm(@RequestBody Map<String, Object> form) {
    throttle.check("confirm");
    return ok(service.redemption(CommerceService.text(form.get("code")), true));
  }
}
