package org.javaup.commerce.persistence;
@com.baomidou.mybatisplus.annotation.TableName("mall_sku")
public class SkuEntity {
 @com.baomidou.mybatisplus.annotation.TableId(type=com.baomidou.mybatisplus.annotation.IdType.INPUT)
 public Long id;
 public Long productId;
 public String name;
 public java.math.BigDecimal price;
 public Integer available;
 public Integer reserved;
 public Integer sold;
 public Integer validDays;
 public Integer version;
 public String saleMode;
}
