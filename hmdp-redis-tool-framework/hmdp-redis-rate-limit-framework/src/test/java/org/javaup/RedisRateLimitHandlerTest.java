package org.javaup;

import org.springframework.beans.factory.annotation.Autowired;
import lombok.extern.slf4j.Slf4j;
import org.javaup.execute.RateLimitHandler;
import org.javaup.ratelimit.extension.RateLimitScene;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@Slf4j
@SpringBootTest
class RedisRateLimitHandlerTest {
    
    @Autowired
    private RateLimitHandler rateLimitHandler;

    @Test
    void test1() throws InterruptedException {
        rateLimitHandler.execute(1L, 1987041610793484289L, RateLimitScene.SECKILL_ORDER);
    }
   
}
