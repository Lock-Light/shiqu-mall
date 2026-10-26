package org.javaup.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.config.RetryInterceptorBuilder;
import org.springframework.boot.autoconfigure.amqp.SimpleRabbitListenerContainerFactoryConfigurer;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.context.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import static org.javaup.constant.Constant.*;
@Configuration
public class LegacyRabbitConfig {
 @Bean("legacyOrderQueue")public String orderQueue(@Value("${prefix.distinction.name:hmdp}")String p){return p+"-"+SECKILL_VOUCHER_TOPIC;}
 @Bean("legacyInvalidationQueue")public Queue invalidationQueue(@Value("${prefix.distinction.name:hmdp}")String p){return new AnonymousQueue(java.util.Map.of("x-dead-letter-exchange",p+"-"+SECKILL_VOUCHER_CACHE_INVALIDATION_TOPIC+".DLQ"));}
 @Bean("legacyDeadQueue")public String deadQueue(@Value("${prefix.distinction.name:hmdp}")String p){return p+"-"+SECKILL_VOUCHER_CACHE_INVALIDATION_TOPIC+".DLQ";}
 @Bean public Declarables legacyQueues(@Value("${prefix.distinction.name:hmdp}")String p,@org.springframework.beans.factory.annotation.Qualifier("legacyInvalidationQueue")Queue local){
  String order=p+"-"+SECKILL_VOUCHER_TOPIC,invalid=p+"-"+SECKILL_VOUCHER_CACHE_INVALIDATION_TOPIC;
  var oe=new FanoutExchange(order,true,false);var ie=new FanoutExchange(invalid,true,false);var od=new FanoutExchange(order+".DLQ",true,false);var id=new FanoutExchange(invalid+".DLQ",true,false);
  var oq=QueueBuilder.durable(order).deadLetterExchange(order+".DLQ").build();var dq=new Queue(order+".DLQ",true);var iq=new Queue(invalid+".DLQ",true);
  return new Declarables(oe,ie,od,id,oq,dq,iq,BindingBuilder.bind(oq).to(oe),BindingBuilder.bind(local).to(ie),BindingBuilder.bind(dq).to(od),BindingBuilder.bind(iq).to(id));
 }
 @Bean("rabbitListenerContainerFactory")public SimpleRabbitListenerContainerFactory factory(ConnectionFactory c,SimpleRabbitListenerContainerFactoryConfigurer configurer){
  var f=new SimpleRabbitListenerContainerFactory();configurer.configure(f,c);f.setAcknowledgeMode(AcknowledgeMode.MANUAL);f.setDefaultRequeueRejected(false);f.setPrefetchCount(10);
  f.setAdviceChain(RetryInterceptorBuilder.stateless().maxAttempts(4).backOffOptions(300,2,2000).recoverer((message,cause)->{throw new org.springframework.amqp.AmqpRejectAndDontRequeueException("重试次数已用尽，拒绝并转入死信队列",true,cause);}).build());return f;
 }
}
