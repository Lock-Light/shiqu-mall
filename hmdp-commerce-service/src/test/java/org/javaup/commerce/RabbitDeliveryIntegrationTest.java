package org.javaup.commerce;

import static org.junit.jupiter.api.Assertions.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.*;

/** Uses the real broker and an isolated temporary binding; calls the production publisher. */
class RabbitDeliveryIntegrationTest {
  @Test void confirmsPersistentPublishAndRejectsMandatoryReturn() throws Exception {
    var connection = new CachingConnectionFactory("rabbitmq", 5672);
    connection.setUsername("shiqu"); connection.setPassword("shiqu-local");
    connection.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.CORRELATED);
    connection.setPublisherReturns(true);
    String name = "migration-probe-" + UUID.randomUUID();
    var admin = new RabbitAdmin(connection);
    var exchange = new DirectExchange(name, true, false);
    var queue = new Queue(name, true, false, false);
    var binding = BindingBuilder.bind(queue).to(exchange).with("order");
    try {
      admin.declareExchange(exchange); admin.declareQueue(queue); admin.declareBinding(binding);
      var template = new RabbitTemplate(connection); template.setMandatory(true);
      var publisher = new CommerceMessaging();
      var field = CommerceMessaging.class.getDeclaredField("template");
      field.setAccessible(true); field.set(publisher, template); publisher.exchange = name;
      publisher.send("confirmed-message", "real-broker-probe");
      var received = template.receive(name, 3000);
      assertNotNull(received);
      assertEquals("confirmed-message", received.getMessageProperties().getMessageId());
      assertEquals(MessageDeliveryMode.PERSISTENT, received.getMessageProperties().getReceivedDeliveryMode());
      admin.removeBinding(binding);
      // The exchange confirms receipt, but mandatory return means no queue accepted it.
      assertThrows(IllegalStateException.class, () -> publisher.send("unroutable", "must-fail"));
    } finally {
      admin.deleteQueue(name); admin.deleteExchange(name); connection.destroy();
    }
  }
}
