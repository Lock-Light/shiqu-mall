package org.javaup.commerce;
import jakarta.servlet.http.*;
import org.javaup.utils.UserHolder;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.servlet.*;
import org.springframework.web.servlet.config.annotation.*;
@Configuration
public class CommerceWebConfig implements WebMvcConfigurer {
 @Autowired private CoreDirectoryClient directory;
 public void addInterceptors(InterceptorRegistry registry){registry.addInterceptor(new HandlerInterceptor(){
  public boolean preHandle(HttpServletRequest req,HttpServletResponse res,Object h){
   UserHolder.removeUser();
   String p=req.getRequestURI(),token=req.getHeader("Authorization");
   if(token!=null&&!token.isBlank())UserHolder.saveUser(directory.session(token));
   if(p.equals("/actuator/health") || ("GET".equals(req.getMethod()) && (p.equals("/mall/products")||p.matches("/mall/products/[0-9]+")||p.matches("/mall/skus/[0-9]+/quote")||p.matches("/mall/shops/[0-9]+")||p.equals("/mall/stories")||p.equals("/mall/places"))))return true;
   if(UserHolder.getUser()!=null)return true;res.setStatus(401);return false;
  }
  public void afterCompletion(HttpServletRequest r,HttpServletResponse s,Object h,Exception e){UserHolder.removeUser();}
 });}
}
