"""Integration acceptance against this project's isolated Compose environment.

Creates labelled demo fixtures; never clears business data or other projects.
Tokens are saved only in ignored .runtime/ for the browser acceptance script.
"""
import concurrent.futures, datetime, json, os, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('PLUS_URL','http://localhost:18091')
ISOLATED=BASE in ('http://127.0.0.1:18092','http://localhost:18092')
RESULTS=[]
sys.stdout.reconfigure(encoding='utf-8')

def call(path, method='GET', body=None, token='', ok=True):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']=token
    req=Request(BASE.replace('localhost','127.0.0.1')+'/api'+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else (b'' if method in ('POST','PUT') else None),headers=headers,method=method)
    try:
        with urlopen(req,timeout=20) as r: result=json.load(r)
    except HTTPError as e:
        result={'http':e.code,'success':False}
    if ok: assert result.get('success'), (path,result)
    return result

def data(path,method='GET',body=None,token=''):
    return call(path,method,body,token).get('data')

def check(name,fn):
    try:
        detail=fn()
        RESULTS.append({'name':name,'passed':True,'detail':detail})
        print('PASS',name,detail or '',flush=True)
        return detail
    except Exception as e:
        RESULTS.append({'name':name,'passed':False,'error':str(e)})
        print('FAIL',name,str(e),flush=True)
        return None

def require(value,message='assertion failed'):
    assert value,message

def login(phone):
    code=str(data('/user/code?'+urlencode({'phone':phone}),'POST'))
    assert len(code)==6 and code.isdigit(),code
    token=data('/user/login','POST',{'phone':phone,'code':code})
    assert not call('/user/login','POST',{'phone':phone,'code':code},ok=False)['success'],'OTP reused'
    return {'phone':phone,'token':token,'user':data('/user/me',token=token)}

def docker(*args):
    if ISOLATED:
        if len(args)>=3 and args[:3]==('exec','-T','redis'):
            return subprocess.check_output(['docker','compose','-f','compose.commerce-test.yaml','exec','-T','test-redis',*args[3:]],cwd=ROOT,encoding='utf-8',stderr=subprocess.DEVNULL).strip()
        args=tuple(str(a).replace('hmdp_0','hmdp_test_0').replace('hmdp_1','hmdp_test_1') for a in args)
    return subprocess.check_output(['docker','compose',*args],cwd=ROOT,encoding='utf-8',stderr=subprocess.DEVNULL).strip()

def redis(*args):
    return docker('exec','-T','redis','redis-cli','--no-auth-warning','-a','plus-local',*map(str,args))

def physical_rows(table,where):
    queries=[f'SELECT * FROM hmdp_{db}.{table}_{tb} WHERE {where}' for db in range(2) for tb in range(2)]
    return docker('exec','-T','mysql','mysql','-uhmdp','-pplus-local','--batch','-e',';'.join(queries))

def buy(voucher,token):
    # Respect the upstream token bucket, including the shared IP/user quotas.
    for attempt in range(3):
        issued=call('/voucher-order/seckill/token/'+voucher,token=token,ok=False)
        if issued.get('success'):
            result=call('/voucher-order/seckill/'+voucher+'?'+urlencode({'accessToken':issued['data']}),'POST',token=token,ok=False)
        else:result=issued
        if '频繁' not in str(result.get('errorMsg','')):return result
        if attempt<2:time.sleep(26)
    return result

def poll_order(order,token):
    for _ in range(40):
        result=data('/voucher-order/get/seckill/voucher/order-id','POST',{'orderId':order},token)
        if result: return str(result)
        time.sleep(.25)
    raise AssertionError('RabbitMQ order did not commit within 10s: '+order)

def main():
    assert ISOLATED,'Legacy regression creates fixtures: use PLUS_URL=http://127.0.0.1:18092; never seed acceptance data into the demo site.'
    run=datetime.datetime.now().strftime('%m%d%H%M%S')
    fixture={'run':run,'base':BASE}
    evidence=ROOT/'docs/evidence';evidence.mkdir(parents=True,exist_ok=True)
    try:
        check('public/protected separation',lambda: require(data('/shop-type/list') and call('/user/me',ok=False).get('http')==401 and call('/blog','POST',{},ok=False).get('http')==401))
        hot=data('/blog/hot?current=1');original=next(b for b in hot if '<br' in b['content'])
        fixture['originalBlog']=original;fixture['originalUser']=str(original['userId'])
        check('public original content and profiles',lambda: require(data('/blog/'+str(original['id']))['content']==original['content'] and data('/user/profile/'+fixture['originalUser'])['nickName']))
        a=login('139'+run[-8:]);b=login('138'+run[-8:]);fixture['a']=a;fixture['b']=b
        check('two OTP logins, consumed code and long IDs',lambda: require(int(a['user']['id'])>2**53 and a['user']['id']!=b['user']['id']))
        at,bt=a['token'],b['token'];aid,bid=str(a['user']['id']),str(b['user']['id'])
        # 管理写入由平台演示账号执行；普通买家只做本人业务，不再绕过新权限要求。
        admin=login('18000000001')['token']
        def profile():
            for token,name in [(at,'验收作者'+run),(bt,'验收读者'+run)]:
                data('/user/profile','PUT',{'nickName':name,'icon':'','introduce':'探店第一行\n第二行','city':'杭州','gender':False,'birthday':'2000-01-02'},token)
                me=data('/user/me',token=token);info=data('/user/info/'+str(me['id']))
                assert me['nickName']==name and info['city']=='杭州' and info['birthday']=='2000-01-02',(me,info)
            assert not call('/user/profile','PUT',{'nickName':'','birthday':'2099-01-01'},at,ok=False)['success']
            assert not call('/user/connections/'+aid+'?kind=fans',token=bt,ok=False)['success']
            return {'author':aid,'reader':bid}
        check('editable sharded profile, fresh /me and ownership',profile)
        def geo():
            shop=data('/shop/1');found=[];dist=[]
            for page in range(1,8):
                rows=data('/shop/of/type?'+urlencode({'typeId':1,'current':page,'x':shop['x'],'y':shop['y']}))
                found.extend(str(s['id']) for s in rows);dist.extend(float(s['distance']) for s in rows)
                if len(rows)<5: break
            assert len(found)==len(set(found)) and dist==sorted(dist) and found and not data('/shop/of/type?typeId=1&x=0&y=0')
            assert not data('/shop/of/type?typeId=1&current=999&x='+str(shop['x'])+'&y='+str(shop['y']))
            assert not call('/shop/of/type?typeId=1&x=999&y=1',ok=False)['success']
            for field in ('comments','score'):
                rows=data('/shop/of/type?typeId=1&sortBy='+field)
                assert [int(s[field]) for s in rows]==sorted([int(s[field]) for s in rows],reverse=True)
            assert data('/shop/of/name?'+urlencode({'name':shop['address'][:4]}))
            assert not call('/shop/99999999',ok=False)['success']
            return {'nearby':len(found),'orderedDistances':dist}
        check('GEO actual distance, pagination, sorting and address search',geo)
        def cache_update():
            sid=str(data('/shop','POST',{'name':'验收商户'+run,'typeId':99,'images':original['images'].split(',')[0],'area':'演示区','address':'验收地址','x':120.149192,'y':30.316078,'avgPrice':30,'openHours':'10:00-20:00'},admin))
            fixture['cacheShop']=sid
            assert data('/shop/'+sid)['name']=='验收商户'+run
            data('/shop','PUT',{'id':sid,'name':'更新后商户'+run,'typeId':98,'x':120.15,'y':30.32},admin)
            assert data('/shop/'+sid)['name']=='更新后商户'+run
            def nearby_ids(type_id,x,y):
                # Prior runs keep their fixtures. Equal-distance results have no
                # insertion-order guarantee, so inspect every returned page.
                ids=set()
                for page in range(1,101):
                    rows=data('/shop/of/type?'+urlencode({'typeId':type_id,'x':x,'y':y,'current':page}))
                    if not rows:return ids
                    ids.update(str(row['id']) for row in rows)
                raise AssertionError('GEO fixture scan exceeded 100 pages')
            assert sid not in nearby_ids(99,120.149192,30.316078),'updated shop remains in old GEO category'
            assert sid in nearby_ids(98,120.15,30.32),'updated shop missing from new GEO category'
            assert not redis('ZSCORE','shop:geo:99',sid),'old GEO membership was not removed'
            assert redis('ZSCORE','shop:geo:98',sid),'new GEO membership was not added'
            return 'new shop → cached read → DB commit → Plus key invalidated; GEO moved category'
        check('cache update invalidation and current GEO index',cache_update)
        def sign():
            data('/user/sign','POST',token=at);n=int(data('/user/sign/count',token=at));data('/user/sign','POST',token=at)
            assert n>=1 and int(data('/user/sign/count',token=at))==n
            return n
        check('Bitmap sign and idempotence',sign)
        def social():
            data('/follow/'+aid+'/true','PUT',token=bt);data('/follow/'+aid+'/true','PUT',token=bt)
            assert data('/follow/or/not/'+aid,token=bt) is True
            assert int(data('/user/profile/'+aid)['fans'])==1
            assert not call('/follow/'+bid+'/true','PUT',token=bt,ok=False)['success']
            assert data('/user/connections/'+bid+'?kind=following',token=bt)[0]['id']==aid
            notes=[]
            for i in range(12):
                notes.append(str(data('/blog','POST',{'title':f'验收{run} 笔记{i+1:02d}','content':'第一行<br/>第二行\\n第三行\n<img src=x onerror="window.__xss=1">','images':original['images'].split(',')[0],'shopId':1,'liked':999,'userId':bid},at)))
            fixture['notes']=notes
            own=data('/blog/of/me?current=1',token=at)+data('/blog/of/me?current=2',token=at)
            assert [str(v['id']) for v in own]==list(reversed(notes))
            assert all(str(v['userId'])==aid and int(v['liked'])==0 for v in own)
            # Force a genuine equal-score boundary in this fixture user's inbox only.
            score=int(time.time()*1000)-1
            redis('ZADD','feed:'+bid,*[v for n in notes for v in (score,n)])
            cursor={'lastId':int(time.time()*1000)+1,'offset':0};seen=[]
            for _ in range(9):
                result=data('/blog/of/follow?'+urlencode(cursor),token=bt) or {}
                rows=result.get('list') or [];seen.extend(str(v['id']) for v in rows)
                if not rows: break
                cursor={'lastId':result['minTime'],'offset':result['offset']}
            assert len(seen)==12 and len(set(seen))==12 and set(seen)==set(notes),seen
            note=notes[-1]
            data('/blog/like/'+note,'PUT',token=bt)
            assert data('/blog/'+note,token=bt)['isLike'] is True
            assert data('/blog/likes/'+note)[0]['id']==bid
            data('/blog/like/'+note,'PUT',token=bt)
            assert data('/blog/'+note,token=bt)['isLike'] is False
            return {'notes':len(notes),'tiedScoreFeed':len(seen)}
        check('follow idempotence, publish, own paging, equal-score Feed and likes',social)
        def create_coupon(stock=3,title='秒杀',start='2020-01-01 00:00:00',end='2037-12-31 00:00:00'):
            return str(data('/voucher/seckill','POST',{'shopId':1,'title':'验收'+run+title,'subTitle':'本地实测券','rules':'仅限堂食\\n每桌限用一张<br/>不与其他优惠同享','payValue':50,'actualValue':100,'type':1,'status':1,'stock':stock,'beginTime':start,'endTime':end,'minLevel':0,'allowedLevels':''},admin))
        def seckill():
            vid=create_coupon();fixture['voucher']=vid
            rows=data('/voucher/list/1');assert len({r['id'] for r in rows})==len(rows)
            item=next(r for r in rows if r['id']==vid);assert int(item['stock'])==3 and int(item['payValue'])==50
            assert not call('/voucher-order/seckill/'+vid,'POST',token=at,ok=False)['success']
            result=buy(vid,at);assert result['success'],result
            oid=str(result['data']);fixture['order']=oid
            assert poll_order(oid,at)==oid
            assert data('/voucher-order/get/seckill/voucher/order-id','POST',{'orderId':oid},bt) is None
            mine=data('/voucher-order/mine',token=at);assert any(o['id']==oid for o in mine)
            duplicate=buy(vid,at)
            assert not duplicate['success'] and '频繁' not in duplicate.get('errorMsg',''),duplicate
            assert str(oid) in physical_rows('tb_voucher_order',f'id={int(oid)}')
            before=next(r for r in data('/voucher/list/1') if r['id']==vid);assert int(before['stock'])==2
            # Double cancellation must restore exactly one unit, then repurchase works.
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                cancelled=list(pool.map(lambda _:call('/voucher-order/cancel','POST',{'voucherId':vid},at,ok=False),range(2)))
            assert sum(r.get('data') is True for r in cancelled)==1,cancelled
            after=next(r for r in data('/voucher/list/1') if r['id']==vid);assert int(after['stock'])==3,after
            mine=data('/voucher-order/mine',token=at);assert next(o for o in mine if o['id']==oid)['status']=='2'
            again=buy(vid,at);assert again['success'],again;poll_order(str(again['data']),at)
            fixture['order']=str(again['data'])
            return {'voucher':vid,'order':str(again['data']),'initialStock':3,'finalStock':2,'cancelWinners':1}
        check('access token → RabbitMQ → MySQL, order ownership, cancel race and repurchase',seckill)
        def subscription():
            vid=create_coupon(stock=1,title='订阅');fixture['subscriptionVoucher']=vid
            for path,expected in [('/voucher/subscribe',1),('/voucher/unsubscribe',0)]:
                data(path,'POST',{'voucherId':vid},bt)
                rows=data('/voucher/get/subscribe/status/batch','POST',{'voucherIdList':[vid]},bt)
                assert int(rows[0]['subscribeStatus'])==expected,rows
            fixture['futureVoucher']=create_coupon(title='预告',start='2037-01-01 00:00:00')
            fixture['expiredVoucher']=create_coupon(title='已结束',end='2020-12-31 00:00:00')
            assert not buy(fixture['futureVoucher'],bt)['success']
            assert not buy(fixture['expiredVoucher'],bt)['success']
            return {'subscribedThenRemoved':vid}
        check('subscribe/unsubscribe batch status, future and expired activity',subscription)
        def last_stock():
            vid=create_coupon(stock=1,title='末库存竞争')
            tokens=[(token,data('/voucher-order/seckill/token/'+vid,token=token)) for token in (at,bt)]
            # Acquire credentials first, then let the IP bucket refill before the race.
            time.sleep(6)
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                attempts=list(pool.map(lambda pair:(pair[0],call('/voucher-order/seckill/'+vid+'?'+urlencode({'accessToken':pair[1]}),'POST',token=pair[0],ok=False)),tokens))
            winners=[(t,r) for t,r in attempts if r.get('success')]
            assert len(winners)==1,attempts
            assert all(r.get('success') or '库存' in r.get('errorMsg','') for t,r in attempts),attempts
            token,result=winners[0];poll_order(str(result['data']),token)
            assert int(next(v for v in data('/voucher/list/1') if v['id']==vid)['stock'])==0
            return {'stock':1,'successfulBuyers':1,'remainingStock':0}
        check('two buyers racing for final stock cannot oversell',last_stock)
        def logout():
            temp=login('137'+run[-8:]);t=temp['token'];data('/user/logout','POST',token=t)
            assert call('/user/me',token=t,ok=False).get('http')==401
        check('server logout actually revokes token',logout)
    finally:
        runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
        (runtime/'fixtures.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8')
        (runtime/('fixtures-'+run+'.json')).write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8')
        report={'time':datetime.datetime.now().isoformat(),'base':BASE,'checks':RESULTS,'passed':all(r['passed'] for r in RESULTS),'fixtureRun':run}
        (evidence/'migration-legacy-api-commerce.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if RESULTS and all(r['passed'] for r in RESULTS) else 1

if __name__=='__main__': sys.exit(main())
