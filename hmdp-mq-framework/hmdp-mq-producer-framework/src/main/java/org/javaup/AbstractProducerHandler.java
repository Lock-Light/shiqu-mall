package org.javaup;
import com.alibaba.fastjson.JSON;
import java.util.*;
import java.util.concurrent.*;
import org.javaup.message.MessageExtend;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.slf4j.LoggerFactory;
/** Legacy voucher publisher. Callback only after correlated publisher confirm and route acceptance. */
public abstract class AbstractProducerHandler<M extends MessageExtend<?>> {
 @Autowired private RabbitTemplate template;
 public final CompletableFuture<RabbitSendReceipt<M>> sendMqMessage(String destination,M message){return sendRecord(destination,message);}
 public final CompletableFuture<RabbitSendReceipt<M>> sendRecord(String destination,M message){
  var result=new CompletableFuture<RabbitSendReceipt<M>>();var correlation=new CorrelationData(UUID.randomUUID().toString());
  try {
   var p=new MessageProperties();p.setContentType("text/plain");p.setContentEncoding("UTF-8");p.setMessageId(message.getUuid());p.setDeliveryMode(MessageDeliveryMode.PERSISTENT);
   if(message.getHeaders()!=null)message.getHeaders().forEach(p::setHeader);if(message.getKey()!=null)p.setHeader("businessKey",message.getKey());
   template.send(destination,"",new Message(JSON.toJSONBytes(message),p),correlation);
   correlation.getFuture().orTimeout(5,TimeUnit.SECONDS).whenComplete((ack,error)->{
    if(error!=null||!ack.isAck()||correlation.getReturned()!=null){Throwable cause=error!=null?error:new IllegalStateException("RabbitMQ消息拒绝或没有路由");afterSendFailure(destination,message,cause);result.completeExceptionally(cause);}
    else {var receipt=new RabbitSendReceipt<M>(destination,message);afterSendSuccess(receipt);result.complete(receipt);}
   });
  }catch(Exception e){afterSendFailure(destination,message,e);result.completeExceptionally(e);}return result;
 }
 @SuppressWarnings("unchecked") public final <T> CompletableFuture<RabbitSendReceipt<M>> sendPayload(String t,T payload){return sendMqMessage(t,(M)MessageExtend.of(payload));}
 @SuppressWarnings("unchecked") public final <T> CompletableFuture<RabbitSendReceipt<M>> sendPayload(String t,String key,T payload,Map<String,String> headers){return sendRecord(t,(M)MessageExtend.of(payload,key,headers));}
 public final <T> CompletableFuture<Void> sendBatch(String t,List<T> payloads){return CompletableFuture.allOf(payloads.stream().map(p->sendPayload(t,p)).toArray(CompletableFuture[]::new));}
 public final <T> RabbitSendReceipt<M> sendAndWait(String t,T p)throws ExecutionException,InterruptedException{return sendPayload(t,p).get();}
 @SuppressWarnings("unchecked") public final <T> CompletableFuture<RabbitSendReceipt<M>> sendToDlq(String t,T payload,String reason){M m=(M)MessageExtend.of(payload);m.setHeaders(Map.of("dlqReason",reason));return sendRecord(t+".DLQ",m);}
 protected void afterSendSuccess(RabbitSendReceipt<M> result){LoggerFactory.getLogger(getClass()).info("RabbitMQ confirmed destination={}",result.destination());}
 protected void afterSendFailure(String t,M m,Throwable e){LoggerFactory.getLogger(getClass()).error("RabbitMQ publish failed destination={}",t,e);}
}
