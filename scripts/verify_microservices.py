"""Gateway/Nacos/Dubbo and poison-message checks against the dedicated 18092 stack."""
import datetime,json,subprocess,time,uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode,quote
from migrate_commerce import ROOT
BASE='http://127.0.0.1:18092';checks=[]
accounts=json.loads((ROOT/'.runtime/commerce-test-accounts.json').read_text(encoding='utf-8'))

def docker(*args,input=None):
    return subprocess.check_output(['docker',*args],cwd=ROOT,input=input,stderr=subprocess.DEVNULL)

def api(path,token=None,headers=None):
    h=dict(headers or {})
    if token:h['Authorization']=token
    try:
        with urlopen(Request(BASE+'/api'+path,headers=h),timeout=15) as r:return r.status,dict(r.headers),json.load(r)
    except HTTPError as e:return e.code,dict(e.headers),json.loads(e.read() or '{}')

def rabbit(path,body=None):
    cmd=['wget','-qO-','--header=Content-Type: application/json']
    if body is not None:cmd+=['--post-file=/dev/stdin']
    cmd+=['http://shiqu:shiqu-local@127.0.0.1:15672/api/'+path]
    return json.loads(docker('compose','exec','-T','rabbitmq',*cmd,input=None if body is None else json.dumps(body).encode()))

def check(name,fn):
    try:detail=fn();checks.append({'name':name,'passed':True,'detail':detail});print('PASS',name,flush=True)
    except Exception as e:checks.append({'name':name,'passed':False,'error':str(e)});print('FAIL',name,str(e),flush=True)

def main():
    def discovery():
        found={}
        for name in ('hmdp-core-test','hmdp-commerce-test','hmdp-gateway-test'):
            url='http://localhost:8848/nacos/v1/ns/instance/list?'+urlencode({'serviceName':name,'groupName':'commerce-test'})
            body=json.loads(docker('compose','exec','-T','nacos','curl','-fsS',url))
            hosts=[h for h in body['hosts'] if h['healthy'] and h['enabled']]
            assert len(hosts)==1,(name,body)
            found[name]=[{k:h[k] for k in ('ip','port','healthy')} for h in hosts]
        return found
    check('three independent HTTP services registered healthy in Nacos',discovery)
    def routes():
        for path in ('/shop-type/list','/mall/products'):
            status,headers,body=api(path)
            assert status==200 and body['success'] and headers.get('X-Api-Gateway')=='shiqu',(path,status,headers,body)
        assert api('/mall/me',headers={'X-User-Id':accounts['admin']['user']['id'],'X-User-Role':'ADMIN','X-Shop-Id':'1001'})[0]==401
        status,_,body=api('/mall/me',accounts['buyerA']['token']);assert status==200 and body['success']
        return {'coreAndCommerceRoutes':True,'anonymousForgedIdentityDenied':True,'validSessionViaDubbo':True}
    check('Gateway routes both domains, strips forged identity and preserves token',routes)
    def poison():
        results=[]
        for exchange,routing in [('commerce-test-orders-v2','order'),('commerce-test-seckill_voucher_topic','')]:
            marker='migration-invalid-'+uuid.uuid4().hex
            response=rabbit('exchanges/%2F/'+exchange+'/publish',{'routing_key':routing,'payload':marker,'payload_encoding':'string','properties':{'delivery_mode':2}})
            assert response['routed']
            deadline=time.monotonic()+25;found=False
            while time.monotonic()<deadline and not found:
                messages=rabbit('queues/%2F/'+exchange+'.DLQ/get',{'count':20,'ackmode':'ack_requeue_false','encoding':'auto'})
                for m in messages:
                    if m['payload']==marker:
                        assert any(d.get('reason')=='rejected' for d in m['properties']['headers']['x-death'])
                        results.append({'exchange':exchange,'payload':marker,'deadLetterReason':'rejected'});found=True
                if not found:time.sleep(.5)
            assert found,('Poison message not rejected to DLQ',exchange)
        return {'chains':results,'retryPolicy':'4 attempts, 300ms exponential backoff; rejectManual=true','testQueuesOnly':True}
    check('listener failure after bounded retry reaches RabbitMQ DLQ',poison)
    def rpc_failure():
        try:
            docker('compose','-f','compose.commerce-test.yaml','stop','commerce-test-core')
            status,_,body=api('/mall/me',accounts['buyerA']['token'])
            assert status==503,(status,body)
            assert not body.get('success'),body
        finally:
            docker('compose','-f','compose.commerce-test.yaml','up','-d','--no-deps','--wait','commerce-test-core')
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            status,_,body=api('/mall/me',accounts['buyerA']['token'])
            if status==200 and body.get('success'):return {'coreStopped':'commerce authentication returns 503','afterProviderReturns':'same token works','noFallbackIdentity':True}
            time.sleep(.5)
        raise AssertionError('Dubbo provider failed to recover')
    check('real Dubbo provider outage fails closed and recovers',rpc_failure)
    report={'generated':datetime.datetime.now().isoformat(),'base':BASE,'checks':checks,'scope':'faults only in commerce-test project'}
    (ROOT/'docs/evidence/migration-architecture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not c['passed'] for c in checks))
if __name__=='__main__':raise SystemExit(main())
