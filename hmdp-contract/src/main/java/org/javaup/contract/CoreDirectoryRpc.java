package org.javaup.contract;
import java.util.*;
import org.javaup.dto.UserDTO;
/** Read-only RPC contract. HTTP callers cannot supply their own user identity. */
public interface CoreDirectoryRpc {
 UserDTO session(String token);
 Map<String,Object> shop(long id);
 List<Map<String,Object>> shops(Collection<Long> ids);
 List<Map<String,Object>> allShops();
 Map<Long,UserDTO> users(Collection<Long> ids);
 List<Map<String,Object>> stories(int page);
}
