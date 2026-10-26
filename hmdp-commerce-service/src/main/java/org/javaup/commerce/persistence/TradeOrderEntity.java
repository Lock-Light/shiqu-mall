package org.javaup.commerce.persistence;
@com.baomidou.mybatisplus.annotation.TableName("mall_trade_order")
public class TradeOrderEntity {
 @com.baomidou.mybatisplus.annotation.TableId(type=com.baomidou.mybatisplus.annotation.IdType.INPUT)
 public Long id;
 public Long userId;
 public Long shopId;
 public Long skuId;
 public String title;
 public String skuName;
 public String cover;
 public String shopName;
 public String rules;
 public Integer validDays;
 public java.math.BigDecimal amount;
 public String status;
 public String requestKey;
 public String quoteVersion;
 public java.time.LocalDateTime createdAt;
 public java.time.LocalDateTime expiresAt;
}
