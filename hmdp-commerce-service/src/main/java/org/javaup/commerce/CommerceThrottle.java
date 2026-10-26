package org.javaup.commerce;

import static org.javaup.commerce.CommerceProblem.require;

import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

/** 核销码虽不可预测，仍需限制在线试探；INCR和首次设置过期在同一Lua里避免无TTL计数器。 */
@Component
public class CommerceThrottle {
  final CommerceAccess access;
  final StringRedisTemplate redis;

  @Value("${prefix.distinction.name:hmdp}")
  String prefix;

  final DefaultRedisScript<Long> counter =
      new DefaultRedisScript<>(
          "local n=redis.call('INCR',KEYS[1]);if n==1 then redis.call('PEXPIRE',KEYS[1],2000)"
              + " end;return n",
          Long.class);

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceThrottle(CommerceAccess access, StringRedisTemplate redis) {
    this.access = access;
    this.redis = redis;
  }

  public void check(String scene) {
    Long count;
    try {
      count =
          redis.execute(counter, List.of(prefix + ":mall:throttle:" + scene + ":" + access.user()));
    } catch (CommerceProblem e) {
      throw e;
    } catch (Exception e) {
      throw new CommerceProblem(503, "核销服务限流暂不可用，请稍后重试");
    }
    require(count != null && count <= 20, 429, "核销操作过于频繁，请稍后重试");
  }
}
