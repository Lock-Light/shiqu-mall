package org.javaup.commerce;
import java.util.*;
import org.javaup.contract.CoreDirectoryRpc;
import org.javaup.dto.UserDTO;
import org.apache.dubbo.config.annotation.DubboReference;
import org.springframework.stereotype.Component;
@Component
public class CoreDirectoryClient {
 @DubboReference(group="${rpc.group:shiqu}",check=false,timeout=3000,retries=0) private CoreDirectoryRpc rpc;
 public UserDTO session(String token){return rpc.session(token);}
 public Map<String,Object> shop(long id){return rpc.shop(id);}
 public Map<Long,Map<String,Object>> shops(Collection<Long> ids){Map<Long,Map<String,Object>> m=new HashMap<>();for(var s:rpc.shops(ids))m.put(CommerceService.number(s.get("id")),s);return m;}
 public List<Map<String,Object>> allShops(){return rpc.allShops();}
 public Map<Long,UserDTO> users(Collection<Long> ids){return rpc.users(ids);}
 public List<Map<String,Object>> stories(int page){return rpc.stories(page);}
}
