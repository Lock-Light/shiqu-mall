package org.javaup.init;
import org.springframework.beans.factory.annotation.Autowired;
import org.javaup.service.IShopService;
import org.javaup.utils.RedisConstants;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.data.geo.Point;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/** Rebuilds the derived GEO index without resetting orders, stock or activity dates. */
@Component
public class LocalGeoInit implements ApplicationRunner {
    @Autowired private IShopService shops;
    @Autowired private StringRedisTemplate redis;
    @Override public void run(ApplicationArguments args){
        shops.list().forEach(shop->{
            if(shop.getX()!=null&&shop.getY()!=null)
                redis.opsForGeo().add(RedisConstants.SHOP_GEO_KEY+shop.getTypeId(),new Point(shop.getX(),shop.getY()),shop.getId().toString());
        });
    }
}
