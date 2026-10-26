"""Seckill concurrency + recovery faults. Only restarts dedicated test application."""
import datetime,json,os,subprocess,time,uuid
from migrate_commerce import ROOT,sql
from verify_commerce_api import call,product,pay,parallel,ACCOUNTS

RESULTS=[];STATE={}
def docker(*args,input=None):
    return subprocess.check_output(['docker',*args],cwd=ROOT,input=input,stderr=subprocess.DEVNULL)
def redis(*args):
    return docker('compose','-f','compose.commerce-test.yaml','exec','-T','test-redis','redis-cli','--no-auth-warning','-a','plus-local','--raw',*map(str,args)).decode().strip()
def scalar(query):return sql(query,'hmdp_commerce_test').strip()
def base(aid):return 'commerce-test:mall:{'+str(aid)+'}:'
def check(name,fn):
    try:r=fn();RESULTS.append({'name':name,'passed':True,'detail':r});print('PASS',name,flush=True)
    except Exception as e:RESULTS.append({'name':name,'passed':False,'error':str(e)});print('FAIL',name,str(e),flush=True)
def publish(label,stock=1,begin=None):
    p=product('秒杀'+label,stock);now=datetime.datetime.now()
    a=call('/merchant/activities','POST',{'skuId':p['skuId'],'startsAt':(begin or now-datetime.timedelta(minutes=2)).isoformat(timespec='seconds'),'endsAt':(now+datetime.timedelta(days=1)).isoformat(timespec='seconds')},'merchantA')
    return p,a
def reserve(aid,actor='buyerA',expected=200):return call(f'/trade/activities/{aid}/reserve','POST',{'requestKey':uuid.uuid4().hex},actor,expected)
def poll(aid,rid,actor='buyerA',status='CREATED',timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        r=call(f'/trade/activities/{aid}/result?reservationId={rid}',actor=actor)
        if r['status']==status:return r
        time.sleep(.4)
    raise AssertionError(('result did not converge',aid,rid,r))
def wait_stock(aid,stock):
    end=time.monotonic()+15
    while time.monotonic()<end:
        if redis('GET',base(aid)+'stock')==str(stock):return
        time.sleep(.3)
    raise AssertionError(('Redis stock did not converge',redis('GET',base(aid)+'stock')))
def send(aid,rid,raw=None):
    message=raw or json.dumps({'activityId':str(aid),'reservationId':str(rid)})
    response=json.loads(docker('compose','exec','-T','rabbitmq','sh','-c',"wget -qO- --header='Content-Type: application/json' --post-file=/dev/stdin http://shiqu:shiqu-local@127.0.0.1:15672/api/exchanges/%2F/commerce-test-orders-v2/publish",input=json.dumps({'properties':{'delivery_mode':2},'routing_key':'order','payload':message,'payload_encoding':'string'}).encode()))
    assert response.get('routed'),response
def restart(dispatch=True,sync=True,host='rabbitmq'):
    env=dict(os.environ,COMMERCE_TEST_DISPATCH_ENABLED=str(dispatch).lower(),COMMERCE_TEST_SYNC_ENABLED=str(sync).lower(),COMMERCE_TEST_RABBIT_HOST=host)
    subprocess.run(['docker','compose','-f','compose.commerce-test.yaml','up','-d','--force-recreate','--no-deps','--wait','commerce-test-app'],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    docker('compose','-f','compose.commerce-test.yaml','exec','-T','commerce-test-web','openresty','-s','reload')
def main():
    assert scalar('SELECT DATABASE()')=='hmdp_commerce_test'
    def competition():
        p,a=publish('最后一份');aid=a['id'];STATE.update(product=p,activity=a)
        r=reserve(aid);rid=r['reservationId'];assert reserve(aid)['reservationId']==rid
        reserve(aid,'buyerB',409);created=poll(aid,rid);assert created['orderId']==rid;STATE['first']=rid
        call(f'/trade/activities/{aid}/result?reservationId={rid}',actor='buyerB',expected=403)
        q=call('/mall/skus/'+p['skuId']+'/quote');call('/trade/orders','POST',{'skuId':p['skuId'],'quoteVersion':q['quoteVersion'],'requestKey':uuid.uuid4().hex},'buyerB',409)
        assert scalar('SELECT reserved FROM mall_sku WHERE id='+p['skuId'])=='1';return {'activityId':aid,'orderId':rid,'stock':1,'winners':1}
    check('exclusive inventory, one-per-user and result ownership',competition)
    def duplicates():
        aid=STATE['activity']['id'];rid=STATE['first'];send(aid,rid);send(aid,rid);time.sleep(2)
        assert scalar('SELECT COUNT(*) FROM mall_trade_order WHERE id='+rid)=='1'
        assert scalar('SELECT reserved FROM mall_sku WHERE id='+STATE['product']['skuId'])=='1';return {'replayedMessages':2,'orders':1}
    check('duplicate RabbitMQ messages do not reserve twice',duplicates)
    def repurchase():
        aid=STATE['activity']['id'];old=STATE['first'];call('/trade/orders/'+old+'/cancel','POST',{},'buyerA');wait_stock(aid,1)
        r=reserve(aid);rid=r['reservationId'];assert rid!=old;poll(aid,rid)
        send(aid,old);time.sleep(2)
        assert redis('HGET',base(aid)+'buyers',ACCOUNTS['buyerA']['user']['id'])==rid
        assert redis('GET',base(aid)+'stock')=='0'
        paid=pay(rid);assert paid['status']=='PAID';code=paid['redemption']['code']
        assert call('/merchant/redemptions/confirm','POST',{'code':code},'merchantA')['status']=='USED'
        STATE['newOrder']=rid;return {'oldOrderId':old,'newOrderId':rid,'oldMessageCannotReleaseNewQualification':True,'status':'USED'}
    check('cancel, repurchase, late message fencing and pay/redeem',repurchase)
    def future():
        p,a=publish('未开始',begin=datetime.datetime.now()+datetime.timedelta(hours=1));reserve(a['id'],expected=409)
        call('/merchant/activities','POST',{'skuId':p['skuId'],'startsAt':datetime.datetime.now().isoformat(timespec='seconds'),'endsAt':(datetime.datetime.now()+datetime.timedelta(days=1)).isoformat(timespec='seconds')},'merchantB',403)
        return {'earlyDenied':True,'wrongShopDenied':True}
    check('activity time and publisher permissions',future)
    def crash():
        restart(dispatch=False)
        p,a=publish('进程恢复');r=reserve(a['id']);rid=r['reservationId']
        assert scalar('SELECT COUNT(*) FROM mall_trade_order WHERE id='+rid)=='0'
        assert redis('HGET',base(a['id'])+'states',rid)=='PENDING'
        docker('compose','-f','compose.commerce-test.yaml','stop','commerce-test-app')
        restart();poll(a['id'],rid);call('/trade/orders/'+rid+'/cancel','POST',{},'buyerA');wait_stock(a['id'],1)
        return {'reservationId':rid,'beforeStop':'PENDING, no database order','afterRestart':'CREATED'}
    check('process stops after Lua and before RabbitMQ then recovers',crash)
    def connection():
        restart(host='rabbitmq-unavailable')
        p,a=publish('投递断连');r=reserve(a['id']);rid=r['reservationId'];time.sleep(5)
        assert scalar('SELECT COUNT(*) FROM mall_trade_order WHERE id='+rid)=='0';assert redis('HGET',base(a['id'])+'states',rid)=='PENDING'
        restart();poll(a['id'],rid);call('/trade/orders/'+rid+'/cancel','POST',{},'buyerA');wait_stock(a['id'],1)
        return {'reservationId':rid,'publisherConnectionRestored':True,'demoBrokerNeverStopped':True}
    check('RabbitMQ connection failure preserves recoverable reservation',connection)
    def compensation():
        restart(sync=False)
        p,a=publish('回补恢复');r=reserve(a['id']);rid=r['reservationId'];poll(a['id'],rid)
        call('/trade/orders/'+rid+'/cancel','POST',{},'buyerA')
        assert scalar('SELECT available FROM mall_sku WHERE id='+p['skuId'])=='1'
        assert scalar('SELECT sync_pending FROM mall_seckill_result WHERE reservation_id='+rid)=='1'
        assert redis('GET',base(a['id'])+'stock')=='0'
        restart();wait_stock(a['id'],1);send(a['id'],rid);time.sleep(2);assert redis('GET',base(a['id'])+'stock')=='1'
        return {'databaseClosedBeforeRedisRepair':True,'stockAfterRepeatedRepair':1}
    check('durable cancellation compensation after worker recovery',compensation)
    def stale():
        restart(dispatch=False)
        p,a=publish('迟到预占');r=reserve(a['id']);rid=r['reservationId'];key=base(a['id'])+'payloads'
        body=json.loads(redis('HGET',key,rid));body['expiresAt']=(datetime.datetime.now()-datetime.timedelta(seconds=1)).isoformat(timespec='seconds');redis('HSET',key,rid,json.dumps(body))
        restart();poll(a['id'],rid,status='REJECTED');wait_stock(a['id'],1)
        assert scalar('SELECT COUNT(*) FROM mall_trade_order WHERE id='+rid)=='0';return {'injectedExpiredReservation':True,'orders':0,'stockRestored':1}
    check('expired reservation rejects late consumption',stale)
    def stop_activity():
        p,a=publish('停止入口');r=reserve(a['id']);rid=r['reservationId'];poll(a['id'],rid)
        stopped=call('/merchant/activities/'+a['id']+'/stop','POST',{},'merchantA');assert stopped['status']=='STOPPING'
        reserve(a['id'],'buyerB',409)
        call('/trade/orders/'+rid+'/cancel','POST',{},'buyerA');wait_stock(a['id'],1)
        closed=call('/merchant/activities/'+a['id']+'/stop','POST',{},'merchantA');assert closed['status']=='CLOSED'
        return {'noNewQualifications':True,'existingOrderCanClose':True,'stockNotReset':True,'status':'CLOSED'}
    check('activity stop drains reservations without resetting inventory',stop_activity)
    try:
        pass
    finally:
        restart()
    report={'generated':datetime.datetime.now().isoformat(),'schema':'hmdp_commerce_test','checks':RESULTS,'faultsOnlyInTestApp':True}
    (ROOT/'docs/evidence/migration-commerce-seckill.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'.runtime/commerce-seckill-fixtures.json').write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not x['passed'] for x in RESULTS))
if __name__=='__main__':raise SystemExit(main())
