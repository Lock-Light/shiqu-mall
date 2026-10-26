"""Real HTTP + SQL acceptance against port 18092 and dedicated commerce schema only."""
import concurrent.futures, datetime, json, sys, uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from migrate_commerce import ROOT,sql
sys.stdout.reconfigure(encoding='utf-8')
BASE='http://127.0.0.1:18092';RUN=uuid.uuid4().hex[:12];RESULTS=[]
ACCOUNTS=json.loads((ROOT/'.runtime/commerce-test-accounts.json').read_text(encoding='utf-8'))
def call(path,method='GET',body=None,actor=None,expected=200):
    headers={'Content-Type':'application/json'}
    if actor:headers['Authorization']=ACCOUNTS[actor]['token']
    req=Request(BASE+'/api'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=20) as r:status=r.status;result=json.load(r)
    except HTTPError as e:status=e.code;result=json.loads(e.read() or '{}')
    assert status==expected,(path,status,result)
    if expected==200:assert result.get('success'),(path,result)
    return result.get('data')
def scalar(query):return sql(query,'hmdp_commerce_test').strip()
def check(name,fn):
    try:detail=fn();RESULTS.append({'name':name,'passed':True,'detail':detail});print('PASS',name,flush=True)
    except Exception as e:RESULTS.append({'name':name,'passed':False,'error':str(e)});print('FAIL',name,str(e),flush=True)
def product(label,stock=10):
    form={'shopId':'1001','title':'集成验收'+RUN+label,'category':'运动','cover':'/imgs/commerce/sport.svg','description':'隔离HTTP验收夹具','rules':'支付后30天整份核销','status':'ACTIVE','skuName':'单人测试套餐','price':'19.90','validDays':30,'stock':stock}
    return call('/merchant/products','POST',form,'merchantA')
def buy(sku,actor='buyerA',key=None):
    q=call('/mall/skus/'+str(sku)+'/quote')
    return call('/trade/orders','POST',{'skuId':str(sku),'quoteVersion':q['quoteVersion'],'requestKey':key or uuid.uuid4().hex},actor)
def pay(oid,actor='buyerA',outcome='SUCCESS',key=None):return call('/trade/orders/'+str(oid)+'/mock-pay','POST',{'requestKey':key or uuid.uuid4().hex,'outcome':outcome,'amount':'0.01'},actor)
def parallel(fn,n=8):
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:return list(pool.map(fn,range(n)))
def main():
    assert scalar('SELECT DATABASE()')=='hmdp_commerce_test'
    fixture=product('界面商品',30);sku=fixture['skuId'];saved={}
    def catalog():
        p=call('/mall/products/'+str(fixture['id']));assert p['skus'][0]['price']=='19.90';assert call('/mall/products?q='+RUN)['total']!='0'
        assert sql('SELECT COUNT(*) FROM mall_product WHERE id='+str(fixture['id'])).strip()=='0','Fixture leaked to demo database'
        return {'price':p['skus'][0]['price'],'fixtureInDemo':False}
    check('catalog and test schema isolation',catalog)
    def rights():
        call('/trade/orders',expected=401)
        call('/merchant/products?shopId=1001',actor='buyerA',expected=403)
        call('/merchant/products?shopId=1001',actor='merchantB',expected=403)
        call('/platform/members',actor='buyerA',expected=403)
        call('/shop','PUT',{'id':'1001','name':'should not change'},'buyerA',403)
        call('/voucher-order/reconciliation/task/all','POST',{},'buyerA',403)
        return {'denied':6}
    check('anonymous, shop and legacy management permissions',rights)
    def idempotent():
        key=uuid.uuid4().hex;orders=parallel(lambda _:buy(sku,key=key));assert len({o['id'] for o in orders})==1
        saved['order']=orders[0];assert scalar('SELECT COUNT(*) FROM mall_trade_order WHERE request_key='+"'"+key+"'")=='1'
        assert scalar('SELECT reserved FROM mall_sku WHERE id='+str(sku))=='1';return {'orderId':orders[0]['id'],'requests':8}
    check('concurrent duplicate submit reserves once',idempotent)
    def payment():
        oid=saved['order']['id'];failed=pay(oid,outcome='FAILED');assert failed['status']=='WAIT_PAY'
        key=uuid.uuid4().hex;results=parallel(lambda _:pay(oid,key=key));assert all(r['status']=='PAID' for r in results)
        assert results[0]['amount']=='19.90';saved['paid']=results[0]
        assert scalar('SELECT COUNT(*) FROM mall_redemption WHERE order_id='+str(oid))=='1';assert scalar('SELECT sold FROM mall_sku WHERE id='+str(sku))=='1'
        return {'orderId':oid,'actualAmount':results[0]['amount'],'credentials':1}
    check('failed then repeated payment and server amount',payment)
    def ownership():
        oid=saved['order']['id']
        for path,method,body in [(f'/trade/orders/{oid}','GET',None),(f'/trade/orders/{oid}/mock-pay','POST',{'requestKey':uuid.uuid4().hex,'outcome':'SUCCESS'}),(f'/trade/orders/{oid}/cancel','POST',{}),(f'/trade/orders/{oid}/redemption','GET',None)]:call(path,method,body,'buyerB',403)
        return {'denied':4}
    check('order ownership on query, pay, cancel and credential',ownership)
    def redeem():
        code=saved['paid']['redemption']['code'];call('/merchant/redemptions/preview','POST',{'code':code},'merchantB',403)
        results=parallel(lambda _:call('/merchant/redemptions/confirm','POST',{'code':code},'merchantA'))
        assert all(r['status']=='USED' for r in results)
        assert scalar("SELECT COUNT(*) FROM mall_order_event WHERE order_id="+str(saved['order']['id'])+" AND event_type='USED'")=='1';return {'requests':8,'events':1}
    check('cross-shop denial and concurrent single redemption',redeem)
    def timeout():
        o=buy(sku);oid=o['id'];sql("UPDATE mall_trade_order SET expires_at=DATE_SUB(NOW(3),INTERVAL 1 SECOND) WHERE id="+str(oid),'hmdp_commerce_test')
        assert pay(oid)['status']=='CLOSED';parallel(lambda _:call('/trade/orders/'+str(oid)+'/cancel','POST',{},'buyerA'))
        assert scalar("SELECT COUNT(*) FROM mall_stock_movement WHERE order_id="+str(oid)+" AND action='RELEASE'")=='1';return {'orderId':oid,'releaseCount':1}
    check('expiry rejects payment before scanner and releases once',timeout)
    def last_stock():
        p=product('最后库存',1);q=call('/mall/skus/'+p['skuId']+'/quote');body={'skuId':p['skuId'],'quoteVersion':q['quoteVersion']}
        def attempt(i):
            actor='buyerA' if i%2==0 else 'buyerB'
            try:return call('/trade/orders','POST',{**body,'requestKey':uuid.uuid4().hex},actor)
            except AssertionError as e:
                assert '409' in str(e),e;return None
        results=parallel(attempt);assert sum(r is not None for r in results)==1;return {'requests':8,'winners':1}
    check('last inventory competition',last_stock)
    def platform():
        uid=ACCOUNTS['buyerB']['user']['id'];call('/platform/members','POST',{'userId':str(uid),'shopId':'1001','role':'ADMIN'},'admin')
        memberships=call('/mall/me',actor='buyerB');assert not memberships['admin'];assert any(m['role']=='MERCHANT' for m in memberships['memberships'])
        call('/platform/members/'+str(uid)+'/1001','DELETE',actor='admin');call('/merchant/products?shopId=1001',actor='buyerB',expected=403);return {'grantThenRevoke':True,'cannotSelfPromote':True}
    check('platform authorization and revocation',platform)
    def quote_change():
        p=product('变价');q=call('/mall/skus/'+p['skuId']+'/quote')
        sql('UPDATE mall_sku SET price=25.90,version=version+1 WHERE id='+p['skuId'],'hmdp_commerce_test')
        call('/trade/orders','POST',{'skuId':p['skuId'],'quoteVersion':q['quoteVersion'],'requestKey':uuid.uuid4().hex},'buyerA',409)
        return {'staleQuoteRejected':True}
    check('stale quote rejected',quote_change)
    def rate_limit():
        import time
        code=saved['paid']['redemption']['code'];limited=0
        for _ in range(25):
            try:call('/merchant/redemptions/preview','POST',{'code':code},'merchantA')
            except AssertionError as e:
                assert '429' in str(e),e;limited+=1
        assert limited>0,'Expected rate-limit rejection'
        time.sleep(2.1)
        call('/merchant/redemptions/preview','POST',{'code':code},'merchantA')
        return {'rejectedRequests':limited,'recoveredAfterWindow':True}
    check('redemption Lua limit and expiry recovery',rate_limit)
    report={'run':RUN,'generated':datetime.datetime.now().isoformat(),'base':BASE,'schema':'hmdp_commerce_test','checks':RESULTS}
    out=ROOT/'docs/evidence';out.mkdir(exist_ok=True)
    for name in ('migration-commerce-api.json','migration-commerce-api-'+RUN+'.json'):(out/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'.runtime/commerce-ui-fixtures.json').write_text(json.dumps({'base':BASE,'run':RUN,'product':fixture,'accounts':ACCOUNTS},ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not c['passed'] for c in RESULTS))
if __name__=='__main__':raise SystemExit(main())
