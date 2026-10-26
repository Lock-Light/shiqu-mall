"""Rendered UI acceptance. Test port/db only; drops one response to verify request recovery."""
import datetime,json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from migrate_commerce import ROOT,sql
sys.stdout.reconfigure(encoding='utf-8')
F=json.loads((ROOT/'.runtime/commerce-ui-fixtures.json').read_text(encoding='utf-8'));BASE=F['base'];OUT=ROOT/'docs/evidence'
assert BASE=='http://127.0.0.1:18092'
RESULTS=[];ERRORS=[];STATE={}
def check(name,fn,page):
    try:detail=fn();RESULTS.append({'name':name,'passed':True,'detail':detail});print('PASS',name,flush=True)
    except Exception as e:RESULTS.append({'name':name,'passed':False,'error':str(e)});page.screenshot(path=str(OUT/('migration-commerce-failed-'+str(len(RESULTS))+'.png')),full_page=True);print('FAIL',name,str(e),flush=True)
def goto(page,path):page.goto(BASE+path);page.wait_for_load_state('networkidle')
def overflow(page):
    size=page.evaluate('({viewport:innerWidth,content:document.documentElement.scrollWidth})');assert size['content']<=size['viewport']+1,size;return size
def context(browser,actor=None):
    c=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai');page=c.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:ERRORS.append(str(e)))
    goto(page,'/index')
    if actor:page.evaluate('(token)=>localStorage.setItem("Hmdp-User",JSON.stringify({token}))',F['accounts'][actor]['token'])
    return c,page
def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);anon,page=context(browser)
        def catalog():
            expect(page.locator('.mall-card').first).to_be_visible();page.get_by_label('搜索体验商品').fill(F['run']);page.get_by_role('button',name='搜索',exact=True).click();expect(page.locator('.mall-card').first).to_be_visible()
            expect(page.locator('.mall-card').first).to_contain_text(F['run']);goto(page,'/products/'+F['product']['id']);expect(page.get_by_role('button',name='立即购买',exact=True)).to_be_enabled();overflow(page)
            page.screenshot(path=str(OUT/'migration-commerce-product-390.png'),full_page=True)
            return {'productId':F['product']['id']}
        check('catalog search and real product selection',catalog,page)
        def purchase():
            goto(page,'/checkout/'+F['product']['skuId']);expect(page).to_have_url(re.compile('/login\\?redirect='))
            page.get_by_placeholder('请输入手机号').fill(F['accounts']['buyerA']['phone']);page.get_by_role('button',name='获取验证码',exact=True).click();expect(page.get_by_placeholder('请输入验证码')).to_have_value(re.compile('\\d{6}'));page.get_by_role('checkbox').check();page.get_by_role('button',name='登录',exact=True).click()
            expect(page.get_by_role('heading',name='确认体验订单',exact=True)).to_be_visible();expect(page.get_by_role('button',name='提交订单，前往收银台',exact=True)).to_be_disabled();page.get_by_role('checkbox').check();page.screenshot(path=str(OUT/'migration-commerce-checkout-390.png'),full_page=True);page.get_by_role('button',name='提交订单，前往收银台',exact=True).click()
            expect(page).to_have_url(re.compile('/orders/[0-9]+$'));STATE['path']=page.url.replace(BASE,'');expect(page.get_by_role('heading',name='待付款',exact=True)).to_be_visible()
            page.get_by_role('button',name='模拟支付失败',exact=True).click();expect(page.get_by_role('status')).to_contain_text('模拟支付失败');expect(page.get_by_role('heading',name='待付款',exact=True)).to_be_visible();page.get_by_role('button',name='模拟支付成功',exact=True).click();expect(page.get_by_role('heading',name='待使用',exact=True)).to_be_visible()
            STATE['code']=page.locator('.mall-redemption-code').inner_text();assert re.fullmatch('[a-f0-9]{32}',STATE['code']);page.reload();expect(page.locator('.mall-redemption-code')).to_have_text(STATE['code']);overflow(page);page.screenshot(path=str(OUT/'migration-commerce-paid-390.png'),full_page=True)
            return {'orderId':STATE['path'].split('/')[-1],'refreshPreservesCredential':True}
        check('OTP return, submit, failed retry, payment and refresh',purchase,page)
        cb,pb=context(browser,'merchantB')
        def wrongshop():
            goto(pb,'/merchant');pb.get_by_label('凭证码',exact=True).fill(STATE['code']);pb.get_by_role('button',name='查询凭证',exact=True).click();expect(pb.get_by_role('alert')).to_contain_text('无权管理该门店');return {'denied':True}
        check('wrong merchant cannot preview credential',wrongshop,pb)
        ca,pa=context(browser,'merchantA')
        def redeem():
            goto(pa,'/merchant');pa.get_by_label('凭证码',exact=True).fill(STATE['code']);pa.get_by_role('button',name='查询凭证',exact=True).click();expect(pa.get_by_role('button',name='确认核销整份套餐',exact=True)).to_be_enabled();pa.get_by_role('button',name='确认核销整份套餐',exact=True).click();expect(pa.get_by_role('button',name='已核销，重新确认状态',exact=True)).to_be_visible()
            goto(page,STATE['path']);expect(page.get_by_role('heading',name='已完成',exact=True)).to_be_visible();pa.screenshot(path=str(OUT/'migration-commerce-merchant-390.png'),full_page=True);overflow(pa);return {'buyerStatus':'USED'}
        check('merchant redeems and buyer sees completed state',redeem,pa)
        def lost_response():
            goto(page,'/checkout/'+F['product']['skuId']);expect(page.get_by_role('heading',name='确认体验订单')).to_be_visible();page.get_by_role('checkbox').check();keys=[]
            def drop(route):
                if route.request.method=='POST':keys.append(route.request.post_data_json['requestKey']);route.fetch();route.abort('failed')
                else:route.continue_()
            page.route('**/api/trade/orders',drop);page.get_by_role('button',name='提交订单，前往收银台',exact=True).click();expect(page.get_by_role('alert')).to_be_visible();page.unroute('**/api/trade/orders',drop)
            page.get_by_role('button',name='提交订单，前往收银台',exact=True).click();expect(page).to_have_url(re.compile('/orders/[0-9]+$'))
            assert len(keys)==1;count=sql("SELECT COUNT(*) FROM mall_trade_order WHERE request_key='"+keys[0]+"'",'hmdp_commerce_test').strip();assert count=='1'
            page.get_by_role('button',name='取消待支付订单',exact=True).click();expect(page.get_by_role('heading',name='已关闭',exact=True)).to_be_visible();return {'droppedResponseRecovered':True,'orders':1}
        check('lost response retries same order then cancellation',lost_response,page)
        def layouts():
            samples=[]
            for width in (320,390,768,1440):
                page.set_viewport_size({'width':width,'height':900});goto(page,'/index');expect(page.locator('.mall-card').first).to_be_visible();samples.append(overflow(page));page.screenshot(path=str(OUT/f'commerce-home-{width}.png'),full_page=True)
                goto(page,'/products/'+F['product']['id']);expect(page.get_by_role('button',name='立即购买')).to_be_visible();overflow(page)
                goto(page,STATE['path']);expect(page.get_by_role('heading',name='已完成',exact=True)).to_be_visible();overflow(page)
            return samples
        check('home, product and order responsive widths',layouts,page)
        def management():
            pa.set_viewport_size({'width':1440,'height':1000});goto(pa,'/merchant');pa.get_by_role('button',name='新建体验商品',exact=True).click();pa.locator('label').filter(has_text=re.compile('^商品名称')).locator('input').fill('浏览器草稿'+F['run']);pa.locator('label').filter(has_text=re.compile('^体验内容')).locator('textarea').fill('隔离浏览器验收，不显示到演示首页');pa.get_by_role('button',name='保存商品',exact=True).click();expect(pa.get_by_role('status')).to_contain_text('商品已保存');expect(pa.locator('.mall-merchant-product').filter(has_text='浏览器草稿'+F['run'])).to_be_visible();overflow(pa);return {'draftCreated':True}
        check('merchant creates real draft product',management,pa)
        def admin():
            cc,pc=context(browser,'admin')
            try:goto(pc,'/merchant');expect(pc.get_by_role('heading',name='平台门店授权',exact=True)).to_be_visible();expect(pc.get_by_label('管理门店',exact=True)).to_be_visible();overflow(pc)
            finally:cc.close()
            return {'platformPanelVisible':True}
        check('admin sees scoped platform management',admin,page)
        def errors():
            goto(page,'/products/999999999999999999');expect(page.get_by_role('alert')).to_contain_text('记录不存在');page.get_by_role('button',name='重试',exact=True).click();expect(page.get_by_role('alert')).to_be_visible();return {'missingProductHandled':True}
        check('missing product retry does not crash',errors,page)
        def noerrors():assert not ERRORS,ERRORS;return {'pageerrors':0}
        check('no unhandled browser errors',noerrors,page)
        anon.close();ca.close();cb.close();browser.close()
    report={'generated':datetime.datetime.now().isoformat(),'run':F['run'],'base':BASE,'checks':RESULTS,'pageerrors':ERRORS}
    for name in ('migration-commerce-ui.json','migration-commerce-ui-'+F['run']+'.json'):(OUT/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not r['passed'] for r in RESULTS))
if __name__=='__main__':raise SystemExit(main())
