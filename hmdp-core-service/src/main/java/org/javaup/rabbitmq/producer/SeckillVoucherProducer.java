package org.javaup.rabbitmq.producer;

import org.springframework.beans.factory.annotation.Autowired;
import lombok.extern.slf4j.Slf4j;
import org.javaup.AbstractProducerHandler;
import org.javaup.enums.SeckillVoucherOrderOperate;
import org.javaup.rabbitmq.message.SeckillVoucherMessage;
import org.javaup.rabbitmq.redis.RedisVoucherData;
import org.javaup.message.MessageExtend;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.springframework.stereotype.Component;

/**
 * @program: 黑马点评-plus升级版实战项目。添加 阿星不是程序员 微信，添加时备注 点评 来获取项目的完整资料
 * @description: RabbitMQ 生产者：发送秒杀券
 * @author: 阿星不是程序员
 **/
@Slf4j
@Component
public class SeckillVoucherProducer extends AbstractProducerHandler<MessageExtend<SeckillVoucherMessage>> {
    
    @Autowired
    private SnowflakeIdGenerator snowflakeIdGenerator;
    
    
    @Autowired
    private RedisVoucherData redisVoucherData;
    
@Override
    protected void afterSendFailure(final String topic, final MessageExtend<SeckillVoucherMessage> message, final Throwable throwable) {
        super.afterSendFailure(topic, message, throwable);
        long traceId = snowflakeIdGenerator.nextId();
        redisVoucherData.rollbackRedisVoucherData(
                SeckillVoucherOrderOperate.YES,
                traceId,
                message.getMessageBody().getVoucherId(),
                message.getMessageBody().getUserId(),
                message.getMessageBody().getOrderId(),
                message.getMessageBody().getAfterQty(),
                message.getMessageBody().getChangeQty(),
                message.getMessageBody().getBeforeQty());
    }
}
