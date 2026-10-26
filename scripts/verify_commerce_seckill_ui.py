"""Actual merchant publishes activity, buyer queues/pays, merchant redeems."""
import datetime,json,sys
from playwright.sync_api import sync_playwright,expect
from migrate_commerce import ROOT
from verify_commerce_api import product,ACCOUNTS,BASE
sys.stdout.reconfigure(encoding='utf-8')
def main():
    fixture=product('浏览器限量活动',5);checks=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        def page_for(actor):
            c=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai');page=c.new_page();page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/index');page.wait_for_load_state('networkidle');page.evaluate('(token)=>localStorage.setItem("Hmdp-User",JSON.stringify({token}))',ACCOUNTS[actor]['token']);return c,page
        cm,merchant=page_for('merchantA');cb,buyer=page_for('buyerB')
        try:
            merchant.goto(BASE+'/merchant');merchant.wait_for_load_state('networkidle')
            card=merchant.locator('.mall-merchant-product').filter(has=merchant.get_by_role('heading',name=__import__('re').compile('浏览器限量活动'))).first
            # 用唯一商品ID对应标题定位，页面可包含之前验收留下的其他商品。
            title=__import__('urllib.request',fromlist=['urlopen']).urlopen(BASE+'/api/mall/products/'+fixture['id'])
            product_title=json.load(title)['data']['title'];title.close()
            card=merchant.locator('.mall-merchant-product').filter(has_text=product_title)
            card.get_by_role('button',name='建立限量活动',exact=True).click()
            merchant.get_by_role('button',name='确认建立限量活动',exact=True).click();expect(merchant.get_by_role('status')).to_contain_text('限量活动已建立')
            buyer.goto(BASE+'/products/'+fixture['id']);buyer.wait_for_load_state('networkidle');expect(buyer.get_by_role('button',name='抢购限量体验',exact=True)).to_be_visible();buyer.screenshot(path=str(ROOT/'docs/evidence/migration-commerce-seckill-product-390.png'),full_page=True)
            buyer.get_by_role('button',name='抢购限量体验',exact=True).click();expect(buyer).to_have_url(__import__('re').compile('/orders/[0-9]+$'));expect(buyer.get_by_role('heading',name='待付款',exact=True)).to_be_visible();buyer.get_by_role('button',name='模拟支付成功',exact=True).click();expect(buyer.get_by_role('heading',name='待使用',exact=True)).to_be_visible();code=buyer.locator('.mall-redemption-code').inner_text()
            merchant.get_by_label('凭证码',exact=True).fill(code);merchant.get_by_role('button',name='查询凭证',exact=True).click();merchant.get_by_role('button',name='确认核销整份套餐',exact=True).click();expect(merchant.get_by_role('button',name='已核销，重新确认状态',exact=True)).to_be_visible();buyer.reload();expect(buyer.get_by_role('heading',name='已完成',exact=True)).to_be_visible();assert not errors,errors
            checks.append({'name':'merchant activity → real RabbitMQ order → simulated pay → redemption','passed':True,'detail':{'productId':fixture['id'],'orderId':buyer.url.rsplit('/',1)[-1],'pageerrors':0}});print('PASS browser seckill full transaction',flush=True)
        except Exception as e:
            checks.append({'name':'merchant activity → real RabbitMQ order → simulated pay → redemption','passed':False,'error':str(e)});buyer.screenshot(path=str(ROOT/'docs/evidence/migration-commerce-seckill-ui-failed.png'),full_page=True);print('FAIL',str(e),flush=True)
        finally:cm.close();cb.close();browser.close()
    (ROOT/'docs/evidence/migration-commerce-seckill-ui.json').write_text(json.dumps({'generated':datetime.datetime.now().isoformat(),'base':BASE,'checks':checks,'pageerrors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not c['passed'] for c in checks))
if __name__=='__main__':raise SystemExit(main())
