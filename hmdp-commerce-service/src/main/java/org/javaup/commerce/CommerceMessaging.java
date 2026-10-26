package org.javaup.commerce;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.beans.factory.annotation.*;
import org.springframework.stereotype.Component;
/** Publisher confirm + mandatory return are both checked. Pending Redis ledger survives uncertain outcomes. */
@Component
public class CommerceMessaging {
 @Autowired private RabbitTemplate template;
 @Value("${commerce.rabbit.exchange:commerce-orders-v2}") public String exchange;
 @Value("${commerce.rabbit.queue:commerce-orders-v2}") public String queue;
 public void send(String id,String body) throws Exception {
  var c=new CorrelationData(id+"-"+java.util.UUID.randomUUID());
  var properties=new MessageProperties();properties.setContentType("text/plain");properties.setContentEncoding("UTF-8");properties.setDeliveryMode(MessageDeliveryMode.PERSISTENT);properties.setMessageId(id);
  template.send(exchange,"order",new Message(body.getBytes(java.nio.charset.StandardCharsets.UTF_8),properties),c);
  var confirmed=c.getFuture().get(5,TimeUnit.SECONDS);
  if(!confirmed.isAck()||c.getReturned()!=null)throw new IllegalStateException("RabbitMQ投递未确认或无路由");
 }
}
