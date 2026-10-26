package org.javaup.commerce;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import org.mybatis.spring.SqlSessionTemplate;
import org.javaup.commerce.persistence.*;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * 商城读码入口1：固定同库交易边界。 旧券按用户/券等不同键分片，不能假定一次注解事务等于跨库原子事务。
 * 这里由一个私有连接池同时供MyBatis-Plus SqlSession和事务管理器使用，库存/订单/凭证才能整体回滚。 不将它注册为DataSource
 * Bean，避免Boot因发现第二数据源而停止自动配置旧ShardingSphere数据源。
 */
@Component
public class CommerceDatabase {
  private final HikariDataSource pool;
  public final CommerceRepository repo;
  public final TransactionTemplate tx;

  @org.springframework.beans.factory.annotation.Autowired
public CommerceDatabase(
      @Value(
              "${commerce.jdbc-url:jdbc:mysql://mysql:3306/hmdp_0?serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false}")
          String url,
      @Value("${commerce.username:hmdp}") String username,
      @Value("${commerce.password:plus-local}") String password) {
    HikariConfig config = new HikariConfig();
    config.setJdbcUrl(url);
    config.setUsername(username);
    config.setPassword(password);
    config.setMaximumPoolSize(4);
    config.setMinimumIdle(0);
    config.setPoolName("commerce-local-transaction");
    config.setConnectionInitSql("SET time_zone = '+08:00'");
    pool = new HikariDataSource(config);
    try {
      var mybatis = new MybatisConfiguration();
      mybatis.setMapUnderscoreToCamelCase(true);
      mybatis.setCallSettersOnNulls(true);
      mybatis.setLocalCacheScope(org.apache.ibatis.session.LocalCacheScope.STATEMENT);
      mybatis.addMapper(CommerceSqlMapper.class);
      mybatis.addMapper(ProductMapper.class);
      mybatis.addMapper(SkuMapper.class);
      mybatis.addMapper(TradeOrderMapper.class);
      var factory = new MybatisSqlSessionFactoryBean();
      factory.setDataSource(pool); factory.setConfiguration(mybatis);
      var session = new SqlSessionTemplate(factory.getObject());
      repo = new CommerceRepository(session);
    } catch(Exception e) { pool.close(); throw new IllegalStateException("MyBatis-Plus初始化失败",e); }
    tx = new TransactionTemplate(new DataSourceTransactionManager(pool));
    tx.setTimeout(15);
  }

  @PreDestroy
  public void close() {
    pool.close();
  }
}
