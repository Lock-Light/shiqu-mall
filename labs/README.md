# 课程实验

主业务使用 Plus 的 Kafka 秒杀、单 Redis 与 MySQL 分片。Sentinel、Cluster、底层结构和 Linux IO 在随机命名的独立实验容器中验证，不修改主业务的 Redis 配置。

运行 `python scripts/advanced_labs.py`。只清理本轮创建并校验标签的容器；报告写到 `docs/evidence/advanced-labs.json`。可使用 `--only RDB-AOF-fork` 等单项名称；`--report` 可保存单独报告。

实验脚本的初版来自此前本地课程实现，经迁移独立于旧工程；证据在新目录重跑生成，不复制历史通过结论。Java 哨兵/集群连接实验使用本目录独立的 Java17 / Spring Boot3.5.4 测试工程，各拓扑只执行对应的方法，不将跳过的另一个拓扑当作通过。

范围：RDB/AOF/fork、主从全量/增量同步与三哨兵、Cluster六节点扩八节点/256槽迁移/故障转移、Redis6.2与7.4编码差异、RESP socket客户端、List/PubSub/Lua、pipeline/BigKey/慢查询/TTL/淘汰/ACL、两个JVM的synchronized边界、Linux epoll ET/LT、百万UV HyperLogLog。

实验只证明报告中的观察。单机容器模拟不代表跨机房高可用或生产容量评估。

`Redis-client-locks-Stream`另外执行真实Java测试：Hash长ID序列化、租约过期后的Lua安全解锁、Redisson重入/Watchdog/重试/MultiLock，以及Stream的Pending重读和ACK。

多级缓存运行 `python scripts/verify_multilevel.py`。这是独立Boot3.5.4双JVM工程，通过OpenResty Lua、Caffeine、Redis和临时MySQL提供同一商户读模型；Canal消费真正的ROW binlog并失效所有层。脚本在各层分别命中后，直接SQL更新，确认在60秒TTL前看到新值。默认结束清理自己的实验Compose项目，不影响业务18091；`--keep`保留排查。
