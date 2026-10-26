package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;

import java.util.List;
import java.util.Map;
import org.javaup.utils.UserHolder;
import org.springframework.stereotype.Component;

/** 商城读码入口2：登录只说明身份；门店归属必须再由服务端授权表校验。 */
@Component
public class CommerceAccess {
  @org.springframework.beans.factory.annotation.Autowired private CoreDirectoryClient directory;
  private final CommerceDatabase db;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceAccess(CommerceDatabase db) {
    this.db = db;
  }

  public long user() {
    require(UserHolder.getUser() != null, 401, "请先登录");
    return UserHolder.getUser().getId();
  }

  public boolean admin() {
    return db.repo.queryForObject(
            "SELECT COUNT(*) FROM mall_shop_member WHERE user_id=? AND role='ADMIN'",
            Integer.class,
            user())
        > 0;
  }

  public void shop(long shop) {
    require(
        admin()
            || db.repo.queryForObject(
                    "SELECT COUNT(*) FROM mall_shop_member WHERE user_id=? AND shop_id=? AND"
                        + " role='MERCHANT'",
                    Integer.class,
                    user(),
                    shop)
                > 0,
        403,
        "无权管理该门店");
  }

  public void platform() {
    require(admin(), 403, "需要平台管理员权限");
  }

  public List<Map<String, Object>> memberships() {
    var rows=db.repo.queryForList("SELECT shop_id,role FROM mall_shop_member WHERE user_id=?",user());
    var shops=directory.shops(rows.stream().map(row->CommerceService.number(row.get("shop_id"))).distinct().toList());
    rows.forEach(row->row.put("shop_name",shops.getOrDefault(CommerceService.number(row.get("shop_id")),Map.of()).getOrDefault("name","")));
    return rows;
  }
}
