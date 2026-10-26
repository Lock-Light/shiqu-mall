package com.hmdp.course;

import org.junit.jupiter.api.Test;
import org.redisson.Redisson;
import org.redisson.api.*;
import org.redisson.config.Config;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;

/** Every test targets a disposable lab node supplied by advanced_labs.py. */
public class RedisMechanismsTest {
    String host(){String value=System.getenv("LAB_REDIS");assertNotNull(value,"run via advanced_labs.py");return value;}
    RedissonClient client(){Config c=new Config();c.setLockWatchdogTimeout(3000);c.useSingleServer().setAddress("redis://"+host()+":6379");return Redisson.create(c);}
    @Test void hashSerializationAndSafeUnlock() throws Exception {
        LettuceConnectionFactory factory=new LettuceConnectionFactory(host(),6379);factory.afterPropertiesSet();
        try{
            StringRedisTemplate redis=new StringRedisTemplate(factory);
            redis.opsForHash().putAll("lab:token",Map.of("id","2113824199217782786","nickName","Redis用户"));
            redis.expire("lab:token",30,TimeUnit.SECONDS);
            assertEquals("2113824199217782786",redis.opsForHash().get("lab:token","id"));
            assertTrue(redis.getExpire("lab:token")>0);
            redis.opsForValue().set("lab:lease","old",100,TimeUnit.MILLISECONDS);Thread.sleep(180);
            assertTrue(redis.opsForValue().setIfAbsent("lab:lease","new",10,TimeUnit.SECONDS));
            var script=new org.springframework.data.redis.core.script.DefaultRedisScript<Long>("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",Long.class);
            assertEquals(0L,redis.execute(script,java.util.List.of("lab:lease"),"old"));
            assertEquals("new",redis.opsForValue().get("lab:lease"));
            assertEquals(1L,redis.execute(script,java.util.List.of("lab:lease"),"new"));
        }finally{factory.destroy();}
    }
    @Test void reentrantWatchdogAndMultiLock() throws Exception {
        RedissonClient first=client(),second=client();
        try{
            RLock lock=first.getLock("lab:watchdog");lock.lock();lock.lock();assertEquals(2,lock.getHoldCount());
            assertFalse(second.getLock("lab:watchdog").tryLock(100,TimeUnit.MILLISECONDS));
            lock.unlock();Thread.sleep(4200);assertTrue(lock.remainTimeToLive()>0,"watchdog renews beyond original 3-second lease");
            lock.unlock();assertTrue(second.getLock("lab:watchdog").tryLock());second.getLock("lab:watchdog").unlock();
            RLock multi=first.getMultiLock(first.getLock("lab:multi:a"),second.getLock("lab:multi:b"));
            assertTrue(multi.tryLock(1,5,TimeUnit.SECONDS));
            assertTrue(first.getLock("lab:multi:a").isLocked());assertTrue(second.getLock("lab:multi:b").isLocked());multi.unlock();
        }finally{first.shutdown();second.shutdown();}
    }
}
