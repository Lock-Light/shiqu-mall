package org.javaup;
public record RabbitSendReceipt<M>(String destination,M message) {}
