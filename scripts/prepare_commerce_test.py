"""Create test-only legacy schemas once. Never import a DROP script into demo schemas."""
from migrate_commerce import ROOT, sql

sql("CREATE DATABASE IF NOT EXISTS hmdp_commerce_test CHARACTER SET utf8mb4; GRANT ALL ON hmdp_commerce_test.* TO 'hmdp'@'%'")

for n in (0,1):
    schema='hmdp_test_'+str(n)
    exists=sql("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='"+schema+"'").strip()
    if exists=='0':
        sql(f"CREATE DATABASE {schema} CHARACTER SET utf8mb4; GRANT ALL ON {schema}.* TO 'hmdp'@'%'")
        body=(ROOT/f'infra/seed/hmdp_{n}.sql').read_text(encoding='utf-8').replace('hmdp_'+str(n),schema)
        assert f'USE {schema};' in body and 'USE hmdp_0;' not in body and 'USE hmdp_1;' not in body
        sql(body,schema)
        print('created isolated legacy fixture',schema)
    # Core still owns legacy management checks and demo-story lookup. Its test
    # schemas must contain their metadata even though commerce uses a separate test DB.
    sql(f"CREATE TABLE IF NOT EXISTS {schema}.mall_shop_member LIKE hmdp_0.mall_shop_member; CREATE TABLE IF NOT EXISTS {schema}.mall_demo_record LIKE hmdp_0.mall_demo_record")
config=(ROOT/'infra/shardingsphere.yaml').read_text(encoding='utf-8').replace('/hmdp_0?','/hmdp_test_0?').replace('/hmdp_1?','/hmdp_test_1?')
(ROOT/'.runtime').mkdir(exist_ok=True)
(ROOT/'.runtime/shardingsphere-test.yaml').write_text(config,encoding='utf-8')
print('Commerce test config ready; Redis is a separate temporary service.')
