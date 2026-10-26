package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;

import java.util.Map;
import org.javaup.dto.Result;

import org.springframework.web.bind.annotation.*;

/** 平台演示账号只由本地种子初始化；公开注册不能自行选择管理员或商户身份。 */
@RestController
@RequestMapping("/platform")
public class CommercePlatformController {
  final CommerceDatabase db;
  final CommerceAccess access;
  final CoreDirectoryClient directory;

  @org.springframework.beans.factory.annotation.Autowired

  public CommercePlatformController(
      CommerceDatabase db, CommerceAccess access, CoreDirectoryClient directory) {
    this.db = db;
    this.access = access;
    this.directory = directory;
  }

  @GetMapping("/shops")
  public Result<?> shops() {
    access.platform();
    return Result.ok(
        CommerceController.view(
            directory.allShops()));
  }

  @GetMapping("/members")
  public Result<?> members() {
    access.platform();
    var rows=db.repo.queryForList("SELECT user_id,shop_id,role FROM mall_shop_member ORDER BY shop_id,user_id");
    var shops=directory.shops(rows.stream().map(row->CommerceService.number(row.get("shop_id"))).distinct().toList());
    rows.forEach(row->row.put("shop_name",shops.getOrDefault(CommerceService.number(row.get("shop_id")),Map.of()).getOrDefault("name","")));
    return Result.ok(CommerceController.view(rows));
  }

  @PostMapping("/members")
  public Result<?> grant(@RequestBody Map<String, Object> form) {
    access.platform();
    long uid = CommerceService.number(form.get("userId")),
        shop = CommerceService.number(form.get("shopId"));
    require(directory.users(java.util.List.of(uid)).containsKey(uid), 404, "用户不存在，请先使用消费端登录");
    require(
        !directory.shop(shop).isEmpty(),
        404,
        "门店不存在");
    db.repo.update(
        "INSERT IGNORE INTO mall_shop_member(user_id,shop_id,role) VALUES(?,?,'MERCHANT')",
        uid,
        shop);
    return Result.ok(true);
  }

  @DeleteMapping("/members/{user}/{shop}")
  public Result<?> revoke(@PathVariable long user, @PathVariable long shop) {
    access.platform();
    db.repo.update(
        "DELETE FROM mall_shop_member WHERE user_id=? AND shop_id=? AND role='MERCHANT'",
        user,
        shop);
    return Result.ok(true);
  }
}
