package org.javaup.rpc;
import java.util.*;
import java.util.stream.Collectors;
import cn.hutool.core.bean.BeanUtil;
import org.apache.dubbo.config.annotation.DubboService;
import org.javaup.contract.CoreDirectoryRpc;
import org.javaup.dto.UserDTO;
import org.javaup.service.*;
import org.javaup.mapper.CoreDirectoryMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import static org.javaup.utils.RedisConstants.*;
@DubboService(group="${rpc.group:shiqu}",timeout=3000,retries=0)
public class CoreDirectoryProvider implements CoreDirectoryRpc {
 @Autowired private IUserService users;
 @Autowired private IShopService shops;
 @Autowired private CoreDirectoryMapper mapper;
 @Autowired private StringRedisTemplate redis;
 public UserDTO session(String token){
  if(token==null||token.isBlank()) return null;
  var m=redis.opsForHash().entries(LOGIN_USER_KEY+token);
  if(m.isEmpty())return null;
  redis.expire(LOGIN_USER_KEY+token,java.time.Duration.ofMinutes(LOGIN_USER_TTL));
  return BeanUtil.fillBeanWithMap(m,new UserDTO(),false);
 }
 public Map<String,Object> shop(long id){var s=shops.getById(id);return s==null?Map.of():Map.of("id",s.getId(),"name",s.getName(),"address",s.getAddress()==null?"":s.getAddress());}
 public List<Map<String,Object>> shops(Collection<Long> ids){if(ids.isEmpty())return List.of();return shops.listByIds(ids).stream().map(s->(Map<String,Object>)new LinkedHashMap<String,Object>(Map.of("id",s.getId(),"name",s.getName(),"address",s.getAddress()==null?"":s.getAddress()))).toList();}
 public List<Map<String,Object>> allShops(){return mapper.shops();}
 public Map<Long,UserDTO> users(Collection<Long> ids){if(ids.isEmpty())return Map.of();return users.listByIds(ids).stream().collect(Collectors.toMap(u->u.getId(),u->BeanUtil.copyProperties(u,UserDTO.class)));}
 public List<Map<String,Object>> stories(int page){return mapper.stories((page-1)*10);}
}
