package local.hmdp;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import jakarta.annotation.PreDestroy;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/** Isolated course experiment, never used by the Plus business application. */
@SpringBootApplication
@RestController
public class CacheLab {
    final JdbcTemplate jdbc;
    final StringRedisTemplate redis;
    final Cache<Long,Map<String,Object>> cache=Caffeine.newBuilder().maximumSize(1000)
        .expireAfterWrite(60,TimeUnit.SECONDS).recordStats().build();
    final AtomicLong reads=new AtomicLong();
    final String instance=System.getenv().getOrDefault("INSTANCE","app");
    public CacheLab(JdbcTemplate jdbc,StringRedisTemplate redis){this.jdbc=jdbc;this.redis=redis;}
    public static void main(String[] args){SpringApplication.run(CacheLab.class,args);}
    @GetMapping("/health") public String health(){return "UP";}
    @GetMapping("/internal/shop/{id}")
    public ResponseEntity<?> shop(@PathVariable long id){
        Map<String,Object> value=cache.getIfPresent(id);String layer="Caffeine";
        if(value==null){reads.incrementAndGet();value=jdbc.queryForMap("SELECT id,name FROM tb_shop WHERE id=?",id);cache.put(id,value);layer="MySQL";}
        return ResponseEntity.ok().header("X-Cache-Layer",layer).header("X-Instance",instance).body(value);
    }
    @PostMapping("/internal/invalidate/{id}")
    public String invalidate(@PathVariable long id,@RequestHeader("X-Lab-Key") String key){
        if(!"plus-cache-internal".equals(key))throw new IllegalArgumentException("invalid internal key");
        cache.invalidate(id);return "OK";
    }
    @GetMapping("/internal/stats") public Object stats(){return Map.of("instance",instance,"databaseReads",reads.get(),"stats",cache.stats().toString());}
}
