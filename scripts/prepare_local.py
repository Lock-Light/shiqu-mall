"""Prepare isolated local configuration and seed files from the pinned upstream SQL."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
INFRA=ROOT/'infra';INFRA.mkdir(exist_ok=True)
seed=INFRA/'seed';seed.mkdir(exist_ok=True)
for name in ['hmdp_0.sql','hmdp_1.sql']:
    content=(ROOT/'sql'/name).read_text(encoding='utf-8')
    # Upstream dumps reference undefined @saved_* variables in version comments.
    content=re.sub(r'/\*!.*?\*/;?', '',content,flags=re.S)
    (seed/name).write_text('SET NAMES utf8mb4;\n'+content,encoding='utf-8')
sharding=(ROOT/'hmdp-core-service/src/main/resources/shardingsphere.yaml').read_text(encoding='utf-8')
sharding=sharding.replace('127.0.0.1:3306','mysql:3306').replace('username: root','username: hmdp').replace('password: root','password: plus-local')
sharding=sharding.replace('&autoReconnect=true','&autoReconnect=true&allowPublicKeyRetrieval=true&useSSL=false')
sharding=sharding.replace('minimum-idle: 30','minimum-idle: 2').replace('maximum-pool-size: 100','maximum-pool-size: 8')
# Hikari properties are top-level datasource bean properties in ShardingSphere YAML.
sharding=re.sub(r'    hikari:\n(?:      [^\n]*\n)+', '    minimumIdle: 2\n    maximumPoolSize: 8\n    connectionInitSql: "SET time_zone = \'+08:00\'"\n',sharding)
sharding=sharding.replace('      - tb_blog,tb_blog_comments,tb_follow,tb_rollback_failure_log,tb_shop,tb_shop_type,tb_sign',''.join('      - '+name+'\n' for name in ['tb_blog','tb_blog_comments','tb_follow','tb_rollback_failure_log','tb_shop','tb_shop_type','tb_sign']).rstrip())
sharding=sharding.replace('sql-show: true','sql-show: false')
(INFRA/'shardingsphere.yaml').write_text(sharding,encoding='utf-8')
print('Prepared isolated SQL seeds and sharding configuration')
