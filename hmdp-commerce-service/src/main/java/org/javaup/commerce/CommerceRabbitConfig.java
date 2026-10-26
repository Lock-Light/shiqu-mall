package org.javaup.commerce;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.config.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.context.annotation.*;
import org.springframework.beans.factory.annotation.Value;
@Configuration
public class CommerceRabbitConfig {
 @Bean public Declarables commerceQueues(@Value("${commerce.rabbit.exchange:commerce-orders-v2}")String e,@Value("${commerce.rabbit.queue:commerce-orders-v2}")String q){
  var exchange=new DirectExchange(e,true,false);var dlx=new DirectExchange(e+".dead",true,false);
  var queue=QueueBuilder.durable(q).deadLetterExchange(e+".dead").deadLetterRoutingKey("dead").build();var dead=QueueBuilder.durable(q+".DLQ").build();
  return new Declarables(exchange,dlx,queue,dead,BindingBuilder.bind(queue).to(exchange).with("order"),BindingBuilder.bind(dead).to(dlx).with("dead"));
 }
 @Bean("commerceRabbitFactory") public SimpleRabbitListenerContainerFactory commerceFactory(ConnectionFactory connection){
  var f=new SimpleRabbitListenerContainerFactory();f.setConnectionFactory(connection);f.setAcknowledgeMode(AcknowledgeMode.MANUAL);f.setPrefetchCount(10);f.setDefaultRequeueRejected(false);
  f.setAdviceChain(RetryInterceptorBuilder.stateless().maxAttempts(4).backOffOptions(300,2,2000).recoverer((message,cause)->{throw new org.springframework.amqp.AmqpRejectAndDontRequeueException("重试次数已用尽，拒绝并转入死信队列",true,cause);}).build());return f;
 }
}
