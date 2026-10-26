"""Redeem ONE previously created public demo order; does not create orders.

Requires authorized operator SSH access. Privileged OTPs are issued through
the internal core API, never through the public OTP endpoint. Tokens are kept
in memory and revoked on completion. Evidence excludes OTPs and voucher codes.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--order',required=True)
    p.add_argument('--base',default='http://111.228.49.216/dingping')
    p.add_argument('--ssh',default='jdcloud')
    a=p.parse_args()
    if not a.order.isdigit():raise SystemExit('Numeric demo order required')
    base=a.base.rstrip('/')+'/api'
    tokens={};checks=[]
    def call(path,method='GET',body=None,actor=None,expected=200):
        headers={'Content-Type':'application/json'}
        if actor:headers['Authorization']=tokens[actor]
        req=Request(base+path,method=method,headers=headers,data=json.dumps(body).encode() if body is not None else (b'' if method=='POST' else None))
        try:
            response=urlopen(req,timeout=20)
            status=response.status
        except HTTPError as e:response=e;status=e.code
        payload=response.read()
        assert status==expected,(path,status,expected)
        if status==200:
            result=json.loads(payload)
            assert result.get('success'),result.get('errorMsg')
            return result.get('data')
    try:
        for actor,phone in [('buyer','18000000004'),('other','18000000005'),('merchant','18000000002'),('wrongShop','18000000003')]:
            raw=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',a.ssh,'docker','exec','dingping-app-1','curl','-fsS','-X','POST','http://127.0.0.1:8085/user/code?phone='+phone],stderr=subprocess.PIPE)
            code=json.loads(raw)['data']
            tokens[actor]=call('/user/login','POST',{'phone':phone,'code':code})
        oid='/trade/orders/'+a.order
        order=call(oid,actor='buyer')
        assert order['status']=='PAID',order['status']
        voucher=order['redemption']['code']
        call(oid,actor='other',expected=403)
        checks.append('another consumer cannot read this order')
        call('/merchant/redemptions/preview','POST',{'code':voucher},actor='wrongShop',expected=403)
        call('/merchant/redemptions/confirm','POST',{'code':voucher},actor='wrongShop',expected=403)
        assert call(oid,actor='buyer')['status']=='PAID'
        checks.append('wrong shop cannot preview or redeem; order remains paid')
        assert call('/merchant/redemptions/preview','POST',{'code':voucher},actor='merchant')['status']=='PAID'
        assert call('/merchant/redemptions/confirm','POST',{'code':voucher},actor='merchant')['status']=='USED'
        checks.append('authorized shop redeems the paid voucher')
        assert call('/merchant/redemptions/confirm','POST',{'code':voucher},actor='merchant')['status']=='USED'
        final=call(oid,actor='buyer')
        used_events=sum(e['event_type']=='USED' for e in final['events'])
        assert final['status']=='USED' and used_events==1
        checks.append('repeated redemption keeps one USED transition and one audit event')
    finally:
        for actor in tokens:
            call('/user/logout','POST',actor=actor)
    report={'generated':datetime.datetime.now().isoformat(),'base':a.base,'orderId':a.order,'checks':checks,'finalStatus':'USED','usedAuditEvents':1,'operatorSessionsRevoked':len(tokens),'newOrdersCreated':0}
    (ROOT/'docs/evidence/public-deployed-permissions.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
