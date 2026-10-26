"""Publish acceptance totals from actual result files; missing/failed groups fail."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/evidence'
groups=[]
for name,file in [('HTTP integration','api-acceptance.json'),('Browser integration','ui-acceptance.json'),('Redis advanced labs','advanced-labs.json'),('Multilevel/Canal','multilevel-acceptance.json')]:
    path=OUT/file
    if not path.exists():groups.append((name,0,1,file,'missing'));continue
    report=json.loads(path.read_text(encoding='utf-8'))
    if 'checks' in report:
        passed=sum(c['passed'] for c in report['checks']);failed=len(report['checks'])-passed
    elif 'results' in report:
        passed=sum(c['status']=='passed' for c in report['results']);failed=len(report['results'])-passed
    else:passed=int(report.get('passed') is True);failed=1-passed
    groups.append((name,passed,failed,file,report.get('time',report.get('finished_at',''))))
good=all(g[2]==0 and g[1]>0 for g in groups)
lines=['# 测试与验收报告','',f'当前结论：{"所列验收组全部通过" if good else "仍有失败或缺失，不能标记整体通过"}。统计由脚本读取本目录新证据自动生成。','', '| 验收组 | 通过 | 失败/缺失 | 证据 | 生成时间 |','|---|---:|---:|---|---|']
for name,passed,failed,file,date in groups:lines.append(f'| {name} | {passed} | {failed} | [JSON](evidence/{file}) | {date} |')
lines+=['','后端21模块的 `-DskipTests package` 仅证明生产包和测试源码能够编译，不计为业务或单元测试通过。HTTP、浏览器、独立Java/Redis实验和多级缓存联调分别执行。','', '浏览器验收包含原始笔记、规则换行、随机OTP登录、资料头像、上传删除重选、草稿发布、点赞关注、Feed和列表分页、真实Kafka下单/取消、错误重试、过期登录、404及320/390/1440宽度。单次503和图片失败为明确的故障注入，成功流程使用实际接口。','', '高级篇包含真实临时拓扑故障、Spring Boot3 RedisTemplate客户端、Redis6.2/7.4编码差异、百万UV、锁续期/原子解锁、Stream Pending/ACK和Linux epoll。Canal验证采用直接SQL更新，不能用HTTP业务更新冒充binlog同步。','', '复验：`./scripts/dev.ps1 test`、`./scripts/dev.ps1 labs`、`python scripts/verify_multilevel.py`。test先创建新的带标记演示数据，再运行UI。验收数据保存在本项目独立库，脚本不会清空旧项目。','', '结果范围及未接入能力见 [本地修复说明](本地修复说明.md)。测试覆盖不构成生产容量、跨机房HA或所有上游扩展功能的认证。','']
(ROOT/'docs/测试与验收报告.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'allPassed':good,'groups':[{'name':g[0],'passed':g[1],'failed':g[2]} for g in groups]},ensure_ascii=False))
sys.exit(0 if good else 1)
