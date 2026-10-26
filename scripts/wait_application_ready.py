"""Wait for the real Gateway -> discovery -> commerce -> Dubbo read path, not only process health."""
import argparse,json,time
from urllib.request import urlopen
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:18091');p.add_argument('--timeout',type=int,default=90);a=p.parse_args()
deadline=time.monotonic()+a.timeout;last='not checked'
def get(path):
    with urlopen(a.base.rstrip('/')+'/api'+path,timeout=12) as r:
        assert r.headers.get('X-Api-Gateway')=='shiqu','request bypassed Gateway'
        body=json.load(r);assert body.get('success'),body
        return body.get('data')
while time.monotonic()<deadline:
    try:
        assert get('/shop-type/list')
        products=get('/mall/products')['list']
        if products:
            detail=get('/mall/products/'+str(products[0]['id']))
            if detail.get('skus'):get('/mall/skus/'+str(detail['skus'][0]['id'])+'/quote')
        print('Gateway, core HTTP, commerce HTTP and Dubbo catalog reads ready',flush=True)
        break
    except Exception as e:
        last=str(e);time.sleep(1)
else:raise SystemExit('Application routes not ready: '+last)
