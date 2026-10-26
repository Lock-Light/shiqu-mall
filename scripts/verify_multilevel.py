"""Disposable Boot3 / OpenResty / Caffeine / Redis / Canal binlog experiment."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT/'labs/multilevel';OUT=ROOT/'docs/evidence'
BASE='http://127.0.0.1:18092';KEY='plus-cache-internal'
sys.stdout.reconfigure(encoding='utf-8')
def compose(*args):
    p=subprocess.run(['docker','compose',*args],cwd=LAB,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace')
    if p.returncode:raise RuntimeError(p.stdout[-4000:])
    return p.stdout.strip()
def read(path,method='GET'):
    with urlopen(Request(BASE+path,method=method,headers={'X-Lab-Key':KEY}),timeout=5) as r:
        return r.read().decode(),dict(r.headers)
def redis(*args):return compose('exec','-T','redis','redis-cli','--no-auth-warning','-a','cache-local',*args)
def internal(instance,path,post=False):
    return compose('exec','-T',instance,'curl','-fsS',*(['-X','POST'] if post else []),'-H','X-Lab-Key: '+KEY,'http://localhost:8080'+path)
def wait(fn,seconds=60):
    until=time.monotonic()+seconds;last=None
    while time.monotonic()<until:
        try:
            v=fn()
            if v:return v
        except Exception as e:last=e
        time.sleep(.2)
    raise AssertionError('condition timed out: '+str(last))
def update(name):
    compose('exec','-T','mysql','mysql','-ulab','-pcache-local','cache_lab','-e',f"UPDATE tb_shop SET name='{name}' WHERE id=1")
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--keep',action='store_true');args=parser.parse_args()
    report={'time':time.strftime('%Y-%m-%d %H:%M:%S'),'project':'hmdp-plus-cache-lab','passed':False}
    try:
        print('Building isolated Boot3 cache lab',flush=True)
        build=compose('run','--rm','build');(OUT/'multilevel-build.log').write_text(build,encoding='utf-8')
        print('Starting isolated MySQL, Redis, two JVMs, OpenResty and Canal',flush=True)
        compose('up','-d','--wait','mysql','redis','app','app2','edge','canal')
        # Wait for a real binlog event, never infer readiness from container state.
        update('ready-'+str(time.time_ns()));wait(lambda:redis('GET','lab:canal:last-id')=='1')
        for instance in ('app','app2'):internal(instance,'/internal/invalidate/1',True)
        redis('DEL','multilevel:shop:1');read('/_invalidate?id=1')
        layers=[]
        body,headers=read('/multilevel/shop/1');layers.append(headers.get('X-Cache-Layer'))
        body,headers=read('/multilevel/shop/1');layers.append(headers.get('X-Cache-Layer'))
        read('/_invalidate?id=1');body,headers=read('/multilevel/shop/1');layers.append(headers.get('X-Cache-Layer'))
        read('/_invalidate?id=1');redis('DEL','multilevel:shop:1');body,headers=read('/multilevel/shop/1');layers.append(headers.get('X-Cache-Layer'))
        assert layers==['MySQL','OpenResty','Redis','Caffeine'],layers
        # Warm every layer, then update only SQL. No business invalidation API is called.
        for instance in ('app','app2'):internal(instance,'/internal/shop/1')
        redis('DEL','lab:canal:last-id')
        changed='binlog-updated-'+str(time.time_ns());began=time.monotonic();update(changed)
        wait(lambda:redis('GET','lab:canal:last-id')=='1',30)
        body,headers=read('/multilevel/shop/1');assert json.loads(body)['name']==changed,(body,headers)
        assert headers.get('X-Cache-Layer')=='MySQL',headers
        for instance in ('app','app2'):assert json.loads(internal(instance,'/internal/shop/1'))['name']==changed
        elapsed=round(time.monotonic()-began,3)
        assert elapsed<50,'invalidation must precede the 60-second TTL fallback'
        report.update(passed=True,layers=layers,canal={'directSQLUpdate':True,'bothJvmsRefreshed':True,'redisAndOpenRestyInvalidated':True,'observedSeconds':elapsed,'ttlSeconds':60},instances=[json.loads(internal(i,'/internal/stats')) for i in ('app','app2')])
        print('PASS',json.dumps(report,ensure_ascii=False),flush=True)
    except Exception as e:
        report.update(error=str(e),traceback=traceback.format_exc());print('FAIL',str(e),flush=True)
    finally:
        try:(OUT/'multilevel-runtime.log').write_text(compose('logs','--no-color'),encoding='utf-8')
        except Exception:pass
        if not args.keep:
            try:compose('down','--volumes');report['cleanup']='only hmdp-plus-cache-lab project and its disposable anonymous data'
            except Exception as e:report['cleanupError']=str(e)
        (OUT/'multilevel-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())
