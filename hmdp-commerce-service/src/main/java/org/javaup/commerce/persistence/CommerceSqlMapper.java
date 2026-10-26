package org.javaup.commerce.persistence;
import java.util.*;
import org.apache.ibatis.annotations.*;
/** Parameterized custom SQL for joins, row locks and state transitions; never accepts client SQL. */
public interface CommerceSqlMapper {
 @SelectProvider(type=BoundSql.class,method="sql") List<Map<String,Object>> select(@Param("sql") String sql,@Param("args") Object[] args);
 @UpdateProvider(type=BoundSql.class,method="sql") int mutate(@Param("sql") String sql,@Param("args") Object[] args);
 class BoundSql {
  public static String sql(Map<String,Object> p){
   String raw=(String)p.get("sql");StringBuilder out=new StringBuilder();int n=0;boolean quoted=false;
   for(int i=0;i<raw.length();i++){char c=raw.charAt(i);if(c=='\''&&(i==0||raw.charAt(i-1)!='\\'))quoted=!quoted;
    if(c=='?'&&!quoted)out.append("#{args[").append(n++).append("]}");else out.append(c);}
   if(n!=((Object[])p.get("args")).length)throw new IllegalArgumentException("SQL参数数量不匹配");
   return out.toString();
  }
 }
}
