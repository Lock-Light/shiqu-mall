"""Generate content delivery status from real import, browser and regression evidence."""
import datetime, hashlib, json
from collections import Counter
from migrate_commerce import ROOT

OUT=ROOT/'docs/evidence'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
content=read('content-acceptance.json');imported=read('content-import.json');regression=read('commerce-acceptance.json');smoke=read('commerce-demo-smoke.json');runtime=read('commerce-runtime.json')
photos=json.loads((ROOT/'content/photo-manifest.json').read_text(encoding='utf-8'))
now=datetime.datetime.now().isoformat()
assert content['allPassed'] and regression['allPassed'] and imported['protectedStateUnchanged'] and all(c['passed'] for c in smoke['checks'])
assert imported['countsBefore']==imported['countsAfter'] and runtime['deployedJarMatches'] and runtime['testContainersRemaining']==0
checks={'content':len(content['checks']),'regressionItemsAndGroups':sum(g['passed'] for g in regression['groups']),'demoSmoke':len(smoke['checks'])}
licences=dict(Counter(p['license'] for p in photos))
size=sum((ROOT/'hmdp-vue3/public'/p[k].lstrip('/')).stat().st_size for p in photos for k in ('path','thumbnail'))
backup=__import__('pathlib').Path(imported['backup'])
backup_manifest={str(p.name):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in backup.glob('*.sql')}
assert len(backup_manifest)==2
(OUT/'content-backup-manifest.json').write_text(json.dumps({'folder':str(backup),'files':backup_manifest},ensure_ascii=False,indent=2),encoding='utf-8')
manifest=json.loads((OUT/'commerce-version.json').read_text(encoding='utf-8'))
assert manifest['jarSha256']==runtime['jarSha256']
report={'generated':now,'allPassed':True,'counts':imported['countsAfter'],'photos':len(photos),'imageFiles':len(photos)*2,'mediaBytes':size,'licences':licences,'checks':checks,'batch':imported['batch'],'sourceManifest':'commerce-version.json','rawPoiRows':26,'namedPoiRows':25,'manualReview':{'photographsReviewed':40,'detailSamples':4,'sampleTopics':['pingpong','dye','photo','tea'],'rejectedCandidates':['pottery village storefront replaced by actual wheel work','wood pile/nails replaced by hands-on woodworking'],'note':'Visual review of contact sheet and four category screenshots; not a claim of human customer feedback.'}}
(OUT/'content-delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
rows=['# 内容补强验收报告','',f'生成时间：{now}。本轮范围完成并通过所列验收。批次 `{imported["batch"]}`。','',
'## 实际内容与边界','',
'| 内容 | 实际数量/处理 |','|---|---|',
'| 虚构门店 | 32家；运动/手作/文娱/休闲各8家，明确商圈参考坐标、虚构地址、营业时间、介绍、人群和到店提示 |',
'| 商品/SKU | 96商品、192SKU，每类24商品；流程/时长/目标/包含与不含/条件/规则有差异；不是标题加后缀 |',
'| 分享/账号 | 48篇原创演示分享、12演示作者、24条演示账号间关注关系；时间为固定编辑时间轴，不冒充真实消费 |',
f'| 图片 | 40张不同Commons来源照片＋40缩略图，共{size/1024/1024:.2f}MiB；本地文件与哈希，按对应题材/门店复用，不宣称96张独立封面 |',
'| 开放POI | OSM上海有限运动场所原样本26条，中文/英文名称回退后保留25条；1条无名称剔除，保留原始ID/名称/坐标/来源/2026-10-24基准时间 |',
'| 交易保护 | 旧订单、付款、凭证、事件、库存流水、60个旧SKU完整状态与活动哈希前后相同；活动商品800001保留配置，只增添展示图集 |',
'',
'真实OSM场所仅在开放参考页展示，未被伪装成入驻商户，没有虚构套餐、照片、评论、评分或销量。本轮没有新增BI、AI、购物车、真实支付或真实评论模块。',
'','## 实际验收','',
f'- 内容/API/浏览器：{checks["content"]}组通过，详见[JSON](evidence/content-acceptance.json)。覆盖96详情、四类各24商品、80文件响应及哈希、搜索分页、四种宽度、门店/GEO、48分享和作者、25开放POI、署名页，0未处理浏览器异常。',
f'- 普通交易及秒杀/恢复/旧业务联合回归：{checks["regressionItemsAndGroups"]}项/组通过，详见[商城报告](商城测试与验收报告.md)。粒度不同，不称为69个单元测试。',
f'- 18091实际普通付款核销、Lua/Kafka落单取消和部署页面烟测另{checks["demoSmoke"]}组通过，详见[烟测](evidence/commerce-demo-smoke.json)。烟测生成的演示订单保留，没有清库存。',
'- 增量导入重跑前后32/96/192/48/25数量不变，旧交易/库存/活动指纹一致，详见[首次导入](evidence/content-import-initial.json)、[重跑](evidence/content-import.json)。备份两库的路径、字节与SHA256见[备份清单](evidence/content-backup-manifest.json)。',
'- 当前日常5服务，临时测试容器已回收；部署JAR与构建产物SHA256一致，见[资源证据](evidence/commerce-runtime.json)与[源码/内容/测试指纹](evidence/commerce-version.json)。源码含未提交修改，HEAD只代表上游基线。',
'','## 图文目视抽查','',
'已目视检查40张候选缩略图，排除陶艺店外景/木料钉子等不合适首选，改选拉坯与木作现场；四类详情抽查乒乓球、蓝染、摄影、茶席，核对图文题材与版式。照片只展示对应活动/器材，不表述为虚构门店实景。每个题材组1～2图供对应门店三款不同课程使用。',
'','[桌面首页](evidence/content-home-1440.png) · [手机首页](evidence/content-home-390.png) · [四类详情抽查](evidence/content-detail-review.jpg) · [照片总览](evidence/content-contact-sheet.jpg) · [门店](evidence/content-shop-390.png) · [分享](evidence/content-stories-390.png) · [开放场所](evidence/content-open-places-390.png)。',
'','首页默认“多样体验”为确定性交错排序，本轮第一页包含4类与12家不同门店；不是个性化/AI推荐。保留最新上架、价格升降序。',
'','## 来源与实际限制','',
'[逐图许可台账](../content/photo-manifest.json)、[原始许可元数据](../content/photo-source-metadata.json)、[内容清单](../content/catalog.json)、[OSM原样本](../content/poi/shanghai-sports-osm-sample.json)、[复建说明](../content/README.md)。页面署名入口为 /content-sources.html，保留作者、原始文件页、许可链接及WebP/缩略图处理说明；图片衍生文件沿用各自CC许可，与代码Apache许可分开。',
'','开放数据的可用性评估见[选型](../content/dataset-evaluation.md)。本次真正接入的是OSM有限区域样本；Overture/Places为可按bbox抽取的备选，未冒充已下载，Foursquare当前有访问门槛而未使用，ASAP餐饮评论不硬套体验品类。没有已核验可全套导入的中文体验商品/SKU/照片/评论数据包，因此交易内容采用明确演示编辑资料，POI与照片分别核查。',
'','许可分布：'+json.dumps(licences,ensure_ascii=False)+'。OSM原样本及衍生参考表采用ODbL 1.0，署名© OpenStreetMap contributors；不是当前营业情况的认证。',
'','## 实际问题与修复','',
'1. 开放场所首次请求返回业务失败，日志为Rounding necessary：原通用序列化对所有BigDecimal执行setScale(2)。改为保留原精度，金额由DECIMAL(10,2)保持两位。复验全部25条经纬度与原始样本差值小于1e-7，价格格式仍为两位。保留[首次失败](evidence/content-first-failure.json)。',
'2. 一次测试应用重建被本地Docker Engine API以500拒绝；保留[原结果](evidence/commerce-seckill-content-first-failed.json)，后续完整回归通过。未清库、未手工加库存来绕过。',
'3. Commons查询曾限流429，程序按Retry-After等待并串行采集；最终40张到位。后续重建默认固定URL/哈希，来源字节变化时停止，避免搜索排名变化导致换图。',
'','## 入口与复验','',
'- 商城 http://localhost:18091/index；门店 http://localhost:18091/shopList?type=21；分享 http://localhost:18091/discover；真实开放场所 http://localhost:18091/places。',
'- 本轮内容校验：`./.runtime/ui-venv/Scripts/python.exe scripts/verify_content.py`；模拟交易烟测：`./.runtime/ui-venv/Scripts/python.exe scripts/smoke_commerce_demo.py`（会保留真实演示订单，消耗一份普通商品库存）。',
'- 隔离完整回归：`./scripts/commerce.ps1 all`，失败保留现场，排查完成执行stop；不重启旧18090。重新导入/恢复图片见content/README，禁止清空已有交易或活动库存。',
'- 源码：CommerceContent读取展示资料与参考地点；CommerceController保留精度；CommerceService.products提供稳定交错排序；ProductDetail/ShopDetail/ReferencePlaces展示图文；原支付/秒杀主线保留。']
(ROOT/'docs/内容补强验收报告.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
print(json.dumps({'allPassed':True,'counts':report['counts'],'checks':checks},ensure_ascii=True))
