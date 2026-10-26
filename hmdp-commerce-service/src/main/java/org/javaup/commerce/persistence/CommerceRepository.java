package org.javaup.commerce.persistence;
import java.util.*;
import org.mybatis.spring.SqlSessionTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
public class CommerceRepository {
 public final ProductMapper products; public final SkuMapper skus; public final TradeOrderMapper orders;
 private final CommerceSqlMapper sql;
 public CommerceRepository(SqlSessionTemplate s){sql=s.getMapper(CommerceSqlMapper.class);products=s.getMapper(ProductMapper.class);skus=s.getMapper(SkuMapper.class);orders=s.getMapper(TradeOrderMapper.class);}
 public List<Map<String,Object>> queryForList(String q,Object... args){return sql.select(q,args);}
 @SuppressWarnings("unchecked") public <T> T queryForObject(String q,Class<T> type,Object... args){
  var rows=queryForList(q,args);if(rows.isEmpty())throw new EmptyResultDataAccessException(1);Object v=rows.get(0).values().iterator().next();
  if(v instanceof Number n){if(type==Long.class)return (T)Long.valueOf(n.longValue());if(type==Integer.class)return (T)Integer.valueOf(n.intValue());}
  return type.cast(v);
 }
 public int update(String q,Object... args){return sql.mutate(q,args);}
 public void execute(String q){sql.mutate(q,new Object[0]);}
}
