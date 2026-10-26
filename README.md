# Shiqu Mall

基于社区点评项目扩展开发的同城体验商城，支持门店与套餐浏览、普通购买、限时秒杀、订单管理、模拟支付和到店核销，并提供商品管理及门店工作台。

**在线体验：[Shiqu Mall](http://111.228.49.216/dingping/)**

## 主要功能

- 商品 / SKU、服务端报价校验、订单快照与库存预占。
- 模拟支付、取消与超时关闭，通过条件更新及同库事务处理状态竞争。
- Redis Lua 抢购预占、RabbitMQ 异步落单、幂等消费及故障恢复。
- 用户订单归属、门店授权与凭证一次核销。
- 门店缓存 / GEO、关注、点赞及 Feed 滚动分页。
- Gateway 统一接入，Nacos 服务发现，Dubbo 查询会话、用户及门店。
- 保留旧券入口的 IP / 用户双维 Lua 令牌桶限流。

## 技术栈

Java 17、Spring Boot 3、MyBatis-Plus、Spring Cloud Gateway、Dubbo、Nacos、MySQL、Redis、RabbitMQ、Vue 3、Docker Compose。旧业务保留 ShardingSphere 与 Redisson。

## 本地启动

需要 Docker（Linux 容器）、PowerShell 7、Python 3.10+、Node.js 20.19+ 或 22.12+。

```powershell
./scripts/dev.ps1 build
./scripts/dev.ps1 start
python scripts/seed_commerce.py
```

浏览器打开 http://localhost:18091/index 。`seed_commerce.py` 用于首次补充演示商品与账号，不应当作日常重置命令。完整图文内容的复建方式见 [素材与演示内容说明](content/README.md)。

本地 Compose 使用固定开发配置；生产发布脚本在独立副本中生成随机密码，运行数据和生产配置不包含在源码仓库中。

## 源码导航

| 目录 | 内容 |
| --- | --- |
| [hmdp-gateway](hmdp-gateway) | HTTP 网关 |
| [hmdp-core-service](hmdp-core-service) | 用户、会话、门店、社区及旧券业务 |
| [hmdp-commerce-service](hmdp-commerce-service) | 商品、订单、模拟支付、核销与秒杀 |
| [hmdp-contract](hmdp-contract) | RPC 契约及共享 DTO |
| [hmdp-vue3](hmdp-vue3) | Vue 3 商城界面 |
| [infra](infra) | 容器配置、迁移及初始化配置 |
| [scripts](scripts) | 启动、内容导入及验证脚本 |
| [content](content) | 演示内容与素材许可台账 |

实现主线见 [架构说明](docs/architecture.md)。

## 验证入口

```powershell
./scripts/dev.ps1 setup-ui
./scripts/dev.ps1 test
```

专项验证包括事务回滚、重复提交、支付关单竞争、消息重投、秒杀恢复和资源授权。完整验证会启动专用测试环境；原始运行记录与会话不随源码发布。

## 项目来源与许可

本项目基于 [java-up-up/hmdp-plus](https://github.com/java-up-up/hmdp-plus) 二次开发，上游基线为 `03c06cdf325b5063961bf561b40ea8010b03be83`，保留 [Apache License 2.0](LICENSE)。商品交易、模拟付款核销、服务拆分、RabbitMQ 消息迁移及相关验证是本仓库的扩展与修改，详见 [修改说明](MODIFICATIONS.md)。

照片与 OpenStreetMap 数据适用各自许可，来源和署名见 [content](content) 以及前端的 content-sources.html，不以代码许可证替代素材许可。

## 实现范围

支付为模拟，不产生真实扣款；门店与交易套餐是演示内容。当前核心与交易服务共用 MySQL 实例，关键写操作使用同库事务，不描述为分布式写事务。单节点演示与功能验证不等于生产容量或高可用验证。
