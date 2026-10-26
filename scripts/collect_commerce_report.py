"""Build the commerce report only from actual executable evidence, not plan checkboxes."""
import datetime,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from migrate_commerce import ROOT,sql
sys.stdout.reconfigure(encoding='utf-8')
OUT=ROOT/'docs/evidence';OUT.mkdir(exist_ok=True)
generated=datetime.datetime.now().isoformat()
xml=ET.parse(ROOT/'.runtime/commerce-junit/TEST-junit-jupiter.xml').getroot()
junit={'generated':xml.get('timestamp'),'tests':int(xml.get('tests',0)),'failures':int(xml.get('failures',0)),'errors':int(xml.get('errors',0)),'skipped':int(xml.get('skipped',0)),'cases':[t.get('name') for t in xml.findall('testcase')]}
(OUT/'commerce-junit.json').write_text(json.dumps(junit,ensure_ascii=False,indent=2),encoding='utf-8')
groups=[{'name':'真实MySQL事务测试','passed':junit['tests']-junit['failures']-junit['errors']-junit['skipped'],'failed':junit['failures']+junit['errors']+junit['skipped'],'evidence':'commerce-junit.json'}]
for name,file in [('商城HTTP','commerce-api.json'),('商城浏览器','commerce-ui.json'),('秒杀并发/故障恢复','commerce-seckill.json'),('秒杀浏览器闭环','commerce-seckill-ui.json'),('旧业务HTTP回归','legacy-api-commerce.json'),('旧业务浏览器回归','legacy-ui-commerce.json')]:
    data=json.loads((OUT/file).read_text(encoding='utf-8'));checks=data['checks'];groups.append({'name':name,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'evidence':file,'generated':data.get('generated',data.get('time')),'retestedFailedChecks':data.get('retestedFailedChecks',[])})
files=list((ROOT/'hmdp-core-service/src/main/java/org/javaup/commerce').glob('*.java'))+list((ROOT/'hmdp-core-service/src/main/resources/lua').glob('commerce*.lua'))+list((ROOT/'infra/migrations').glob('*.sql'))+list((ROOT/'hmdp-core-service/src/test/java/org/javaup/commerce').glob('*.java'))
files += [p for p in (ROOT/'hmdp-vue3/src').rglob('*') if p.suffix in ('.vue','.js','.css')]
files += [p for p in (ROOT/'scripts').glob('*') if p.suffix in ('.py','.ps1')]
files += [ROOT/'compose.yaml',ROOT/'compose.commerce-test.yaml',ROOT/'hmdp-vue3/package-lock.json',ROOT/'hmdp-vue3/dist/index.html']
files += [ROOT/'hmdp-core-service/src/main/java/org/javaup/config/MvcConfig.java',ROOT/'hmdp-vue3/public/content-sources.html']
files += [p for p in (ROOT/'content').rglob('*') if p.suffix in ('.json','.py','.md')]
files += list((ROOT/'hmdp-vue3/public/imgs/content').glob('*.webp'))
files=sorted(set(files))
version={'collected':generated,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'note':'HEAD为上游基线，改造尚含未提交文件；以下为收集时源码/构建指纹，测试运行时间分别记录，不把源码收集时间当测试时间。','files':{str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'jarSha256':hashlib.sha256((ROOT/'hmdp-core-service/target/hmdp-core-service-0.0.1-SNAPSHOT.jar').read_bytes()).hexdigest()}
(OUT/'commerce-version.json').write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding='utf-8')
queries={'myOrders':'EXPLAIN SELECT * FROM mall_trade_order WHERE user_id=1 ORDER BY id DESC LIMIT 12','expiry':'EXPLAIN SELECT id FROM mall_trade_order WHERE status=\'WAIT_PAY\' AND expires_at<=NOW(3) ORDER BY expires_at LIMIT 100','products':'EXPLAIN SELECT * FROM mall_product WHERE shop_id=1001 ORDER BY id DESC','sync':'EXPLAIN SELECT reservation_id FROM mall_seckill_result WHERE sync_pending=1 ORDER BY reservation_id LIMIT 100'}
plans={name:sql(query,'hmdp_commerce_test').strip() for name,query in queries.items()}
(OUT/'commerce-explain.json').write_text(json.dumps({'generated':generated,'schema':'hmdp_commerce_test','note':'小规模真实演示数据，只作为执行计划观察，不作性能提升或容量结论。','plans':plans},ensure_ascii=False,indent=2),encoding='utf-8')
report={'generated':generated,'groups':groups,'allPassed':all(g['failed']==0 and g['passed']>0 for g in groups),'sourceManifest':'commerce-version.json'}
(OUT/'commerce-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
rows=['# 商城测试与验收报告','',f'生成时间：{generated}。结论：'+('所列验收均通过。' if report['allPassed'] else '存在失败/缺失，不能宣布通过。'),'','| 验收 | 通过 | 失败/跳过 | 证据 |','|---|---:|---:|---|']
rows += [f"| {g['name']} | {g['passed']} | {g['failed']} | [JSON](evidence/{g['evidence']}) |" for g in groups]
rows += ['','源码/构建收集指纹见[版本清单](evidence/commerce-version.json)，执行计划见[EXPLAIN](evidence/commerce-explain.json)。单次运行时间分别保留；原高级实验与原Plus报告为历史证据，不复制为新商城通过。','',
'## 实际验证与边界','',
'事务测试在专用hmdp_commerce_test库运行，清理前校验DATABASE；API/UI使用18092测试应用、独立Redis、测试旧域schema和独立topic，测试订单不进入18091演示库。MySQL进程与Kafka broker复用本项目运行服务，不是独立故障域。',
'','付款失败、重复提交、失去建单响应后的重试、付款/取消竞争、超时关闭、回滚、双用户/门店越权、并发核销均有实际脚本。秒杀故障只重启测试应用、暂停测试投递/同步任务或切断测试应用的Kafka连接，没有停止演示broker。过期预占通过改测试账本期限注入，不冒充等待15分钟的实测。',
'','模拟支付明确不产生真实扣款。暂无退款、预约、物流、多商品合单、生产QPS、真实渠道对账或跨机房认证。Redis终态账本保留复盘，未交付大规模归档；账本缺失保留待办并报错，不自动重置活动库存。',
'','## 主入口部署验证','',
'主入口18091的部署烟测见[JSON](evidence/commerce-demo-smoke.json)：商品数量按当前内容清单校验、普通模拟付款核销、Lua/Kafka落单取消与四种宽度页面。它产生并保留真实演示订单，不加入上表隔离测试的69项/组计数。内容补强的数量、开放照片/POI、图文和浏览器验收另见[内容补强报告](内容补强验收报告.md)。',
'','[运行资源](evidence/commerce-runtime.json)记录日常5服务、测试容器已回收，以及部署JAR与验收产物SHA256一致。内存仅为当时快照，不作为峰值或生产容量结论。主入口截图见[桌面](evidence/commerce-demo-home-1440.png)、[手机](evidence/commerce-demo-home-390.png)及[活动规格](evidence/commerce-demo-product-390.png)。',
'','## 保留的失败与修复','',
'首次真实付款发现DATETIME返回LocalDateTime导致强制Timestamp转换失败，已修正并完成联调。首次回滚测试触发器因权限未执行，改为专用表CHECK约束注入并重跑12项。Surefire运行器下载超时后使用固定JUnit Console实际执行测试；package的skipTests不计测试通过。',
'','前轮旧UI回归有一项仍在/index对笔记接口注入503；首页已迁移后实际应访问/discover。保存首次失败[JSON](evidence/legacy-ui-commerce-first-failed.json)，当时修改用例后只复验失败项；本轮重新执行完整旧UI回归，结果见表。',
'','本轮旧HTTP缓存/GEO回归最初假定新建商户一定排第一，同坐标的历史测试夹具使断言失败。修正为分页确认新分类包含该商户、旧分类不包含，并直接检查Redis两类索引；保存首次失败[JSON](evidence/legacy-api-commerce-first-failed.json)，随后完整重跑旧HTTP/UI回归，最终结果见表。',
'','内容补强期间一次故障注入的Docker重建请求被本机Engine API以500拒绝；保留[首次结果](evidence/commerce-seckill-content-first-failed.json)，随后重新运行完整隔离验收。开放POI首次请求暴露经纬度被统一按金额setScale(2)处理，已修复；实际精度复验见内容报告，不把一次环境失败隐去。',
'','## 复验','',
'日常启动 `./scripts/dev.ps1 start`；首次数据 `python scripts/seed_commerce.py`。完整验收 `./scripts/commerce.ps1 all`，单项见脚本ValidateSet；unit会清理专用商城测试夹具，不改演示库。测试结束 `./scripts/commerce.ps1 stop` 回收测试应用/Redis/网络，数据schema保留。先构建最新前后端再验收；浏览器环境首次运行dev.ps1 setup-ui。']
(ROOT/'docs/商城测试与验收报告.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
print(json.dumps({'groups':groups,'allPassed':report['allPassed']},ensure_ascii=False,indent=2))
raise SystemExit(0 if report['allPassed'] else 1)
