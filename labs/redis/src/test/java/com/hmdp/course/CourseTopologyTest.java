package com.hmdp.course;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Assumptions;
import org.springframework.data.redis.connection.*;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

/** Run while advanced_labs.py has its disposable Sentinel/Cluster topology alive. */
public class CourseTopologyTest {
    @Test void redisTemplateThroughSentinel() {
        String nodes=System.getenv("COURSE_SENTINELS");Assumptions.assumeTrue(nodes!=null,"Only advanced Sentinel lab supplies these nodes");
        RedisSentinelConfiguration config=new RedisSentinelConfiguration().master("course-master");
        for(String node:nodes.split(",")){String[] pair=node.split(":");config.sentinel(pair[0],Integer.parseInt(pair[1]));}
        LettuceConnectionFactory factory=new LettuceConnectionFactory(config);factory.afterPropertiesSet();
        try {StringRedisTemplate redis=new StringRedisTemplate(factory);redis.opsForValue().set("java:sentinel","passed");assertEquals("passed",redis.opsForValue().get("java:sentinel"));}
        finally {factory.destroy();}
    }
    @Test void redisTemplateThroughCluster() {
        String nodes=System.getenv("COURSE_CLUSTER");Assumptions.assumeTrue(nodes!=null,"Only advanced Cluster lab supplies these nodes");
        LettuceConnectionFactory factory=new LettuceConnectionFactory(new RedisClusterConfiguration(Arrays.asList(nodes.split(","))));factory.afterPropertiesSet();
        try {StringRedisTemplate redis=new StringRedisTemplate(factory);redis.opsForValue().set("java:cluster:one","a");redis.opsForValue().set("java:cluster:two","b");assertEquals(Arrays.asList("a","b"),redis.opsForValue().multiGet(Arrays.asList("java:cluster:one","java:cluster:two")));}
        finally {factory.destroy();}
    }
}
