package org.javaup.commerce.persistence;
@com.baomidou.mybatisplus.annotation.TableName("mall_product")
public class ProductEntity {
 @com.baomidou.mybatisplus.annotation.TableId(type=com.baomidou.mybatisplus.annotation.IdType.INPUT)
 public Long id;
 public Long shopId;
 public String title;
 public String category;
 public String cover;
 public String description;
 public String rules;
 public String status;
 public Integer version;
}
