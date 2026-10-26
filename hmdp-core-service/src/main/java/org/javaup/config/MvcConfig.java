package org.javaup.config;
import org.springframework.beans.factory.annotation.Autowired;
import org.javaup.utils.*;
import org.javaup.mapper.CoreDirectoryMapper;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.*;
import jakarta.servlet.http.*;
@Configuration
public class MvcConfig implements WebMvcConfigurer {
 @Autowired private StringRedisTemplate redis;
 @Autowired private CoreDirectoryMapper directory;
 @Override public void addInterceptors(InterceptorRegistry registry){
  registry.addInterceptor(new RefreshTokenInterceptor(redis)).order(0);
  registry.addInterceptor(new HandlerInterceptor(){
   @Override public boolean preHandle(HttpServletRequest req,HttpServletResponse res,Object handler){
    String p=req.getRequestURI();
    if(p.equals("/user/code")||p.equals("/user/login"))return true;
    if("GET".equals(req.getMethod())&&(p.equals("/mall/products")||p.matches("/mall/products/[0-9]+")||p.matches("/mall/skus/[0-9]+/quote")||p.matches("/mall/shops/[0-9]+")||p.equals("/mall/places")||p.equals("/mall/stories")))return true;
    if("GET".equals(req.getMethod())&&(p.equals("/actuator/health")||p.startsWith("/shop/")||p.equals("/shop-type/list")||p.startsWith("/voucher/list/")||p.equals("/blog/hot")||p.matches("/blog/(likes/)?[0-9]+")||p.equals("/blog/of/user")||p.equals("/blog/of/shop")||p.matches("/user/(profile/|info/)?[0-9]+")))return true;
    if(UserHolder.getUser()!=null){
      // 旧管理入口同样收紧：隐藏新工作台按钮并不能阻止直接调用旧教学接口。
      if((!"GET".equals(req.getMethod())&&p.equals("/shop"))||p.equals("/voucher")||p.equals("/voucher/seckill")||p.startsWith("/voucher/update/")||p.equals("/voucher-order/reconciliation/task/all")){if(directory.admin(UserHolder.getUser().getId())==0){res.setStatus(403);return false;}}
      return true;
    }
    res.setStatus(401);return false;
   }
  }).order(1);
 }
}
