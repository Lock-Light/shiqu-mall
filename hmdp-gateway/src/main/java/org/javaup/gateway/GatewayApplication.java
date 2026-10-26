package org.javaup.gateway;
import java.util.UUID;
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.route.*;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Bean;
@SpringBootApplication
public class GatewayApplication {
 public static void main(String[] args){SpringApplication.run(GatewayApplication.class,args);}
 @Bean public RouteLocator routes(RouteLocatorBuilder b,@Value("${routes.core:hmdp-core}")String core,@Value("${routes.commerce:hmdp-commerce}")String commerce){
  return b.routes().route("commerce",r->r.path("/mall/**","/trade/**","/merchant/**","/platform/**").uri("lb://"+commerce))
  .route("core",r->r.path("/**").uri("lb://"+core)).build();
 }
 @Bean public GlobalFilter requestIdentity(){return (exchange,chain)->{
  var request=exchange.getRequest().mutate().headers(h->{h.remove("X-User-Id");h.remove("X-User-Role");h.remove("X-Shop-Id");h.set("X-Request-Id",UUID.randomUUID().toString());}).build();
  exchange.getResponse().getHeaders().set("X-Api-Gateway","shiqu");return chain.filter(exchange.mutate().request(request).build());
 };}
}
