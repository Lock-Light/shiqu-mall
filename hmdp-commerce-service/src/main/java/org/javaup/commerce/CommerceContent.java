package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;

import org.springframework.beans.factory.annotation.Autowired;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.javaup.utils.UserHolder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

/** 图文展示与开放POI不参与交易；真实开放场所不生成商品、核销权限或虚构评价。 */
@Service
public class CommerceContent {
  private final CommerceDatabase db;
  @Autowired private CoreDirectoryClient directory;
  @Autowired private StringRedisTemplate redis;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceContent(CommerceDatabase db) {
    this.db = db;
  }

  public Map<String, Object> decorate(Map<String, Object> product) {
    product.put(
        "gallery",
        db.repo.queryForList(
            "SELECT asset_id,image_url,thumbnail_url,caption FROM mall_product_media WHERE"
                + " product_id=? ORDER BY position",
            product.get("id")));
    product.put("shop_profile", shop(CommerceService.number(product.get("shop_id"))));
    return product;
  }

  public Map<String, Object> shop(long id) {
    var rows = db.repo.queryForList("SELECT * FROM mall_shop_profile WHERE shop_id=?", id);
    if (rows.isEmpty()) return Map.of();
    var profile = rows.get(0);
    profile.put(
        "products",
        db.repo.queryForList(
            "SELECT id,title,cover,category FROM mall_product WHERE shop_id=? AND status='ACTIVE'"
                + " ORDER BY id",
            id));
    return profile;
  }

  public Map<String, Object> places(String q, int page, double x, double y) {
    require(page > 0 && page <= 100 && q.length() <= 80, 400, "查询条件不正确");
    require(
        Double.isFinite(x) && Double.isFinite(y) && Math.abs(x) <= 180 && Math.abs(y) <= 85,
        400,
        "参考坐标不正确");
    String where = " WHERE (?='' OR name LIKE ?)";
    var total =
        db.repo.queryForObject(
            "SELECT COUNT(*) FROM mall_reference_place" + where, Long.class, q, "%" + q + "%");
    var rows =
        db.repo.queryForList(
            "SELECT *,ROUND(ST_Distance_Sphere(POINT(longitude,latitude),POINT(?,?))) distance_m"
                + " FROM mall_reference_place"
                + where
                + " ORDER BY distance_m,source_id LIMIT 12 OFFSET ?",
            x,
            y,
            q,
            "%" + q + "%",
            (page - 1) * 12);
    return Map.of(
        "list",
        rows,
        "total",
        total,
        "page",
        page,
        "attribution",
        "© OpenStreetMap contributors · ODbL 1.0",
        "referenceOnly",
        true);
  }

  public List<Map<String, Object>> stories(int page) {
    require(page > 0 && page <= 1000, 400, "页码不正确");
    var rows = directory.stories(page);
    if(rows.isEmpty())return List.of();
    var authors = directory.users(rows.stream().map(row->CommerceService.number(row.get("user_id"))).distinct().toList());
    return rows.stream()
        .map(
            row -> {
              Map<String, Object> out = new LinkedHashMap<>();
              long uid = CommerceService.number(row.get("user_id"));
              var author = authors.get(uid);
              out.put("id", row.get("id"));
              out.put("shopId", row.get("shop_id"));
              out.put("userId", uid);
              out.put("title", row.get("title"));
              out.put("images", row.get("images"));
              out.put("liked", row.get("liked"));
              out.put("name", author == null ? "演示作者" : author.getNickName());
              out.put("icon", author == null ? "" : author.getIcon());
              out.put(
                  "isLike",
                  UserHolder.getUser() != null
                      && redis
                              .opsForZSet()
                              .score(
                                  "blog:liked:" + row.get("id"),
                                  UserHolder.getUser().getId().toString())
                          != null);
              return out;
            })
        .toList();
  }
}
