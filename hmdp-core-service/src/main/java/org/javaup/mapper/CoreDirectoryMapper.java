package org.javaup.mapper;
import java.util.*;
import org.apache.ibatis.annotations.*;
public interface CoreDirectoryMapper {
 @Select("SELECT id,name FROM tb_shop ORDER BY id DESC") List<Map<String,Object>> shops();
 @Select("SELECT b.* FROM tb_blog b JOIN mall_demo_record r ON r.kind='story' AND r.entity_id=CAST(b.id AS CHAR) ORDER BY b.create_time DESC,b.id DESC LIMIT 10 OFFSET #{offset}") List<Map<String,Object>> stories(int offset);
 @Select("SELECT COUNT(*) FROM mall_shop_member WHERE user_id=#{user} AND role='ADMIN'") int admin(long user);
}
