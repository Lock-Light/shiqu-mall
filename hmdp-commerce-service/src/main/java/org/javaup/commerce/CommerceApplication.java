package org.javaup.commerce;
import org.apache.dubbo.config.spring.context.annotation.EnableDubbo;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.javaup.toolkit.SnowflakeIdGenerator;
@EnableDubbo
@SpringBootApplication
public class CommerceApplication {
 public static void main(String[] args){SpringApplication.run(CommerceApplication.class,args);}
}
