"""Exercise the release under an insecure HTTP origin and a non-root mount.

The optional --trade flag writes one demo order and simulated payment. Without
it, order submission is intercepted and only validates browser request creation.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base',default='http://dingping-preview.test:18094/dingping')
    p.add_argument('--local-resolver',action='store_true')
    p.add_argument('--trade',action='store_true')
    p.add_argument('--label',default='public-prefix-local')
    a=p.parse_args()
    base=a.base.rstrip('/')
    origin=urlparse(base)
    errors=[];failures=[];outside=[];checks=[];order_id=None
    def inspect_response(r):
        parsed=urlparse(r.url)
        if parsed.netloc==origin.netloc:
            if not parsed.path.startswith(origin.path+'/'):
                outside.append(parsed.path)
            if r.status>=400 and not parsed.path.endswith('/trade/orders'):
                failures.append({'url':r.url,'status':r.status})
    with sync_playwright() as pw:
        opts={'headless':True}
        if a.local_resolver:
            opts['args']=['--host-resolver-rules=MAP dingping-preview.test 127.0.0.1','--no-proxy-server']
        browser=pw.chromium.launch(**opts)
        context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai')
        page=context.new_page();page.set_default_timeout(25000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',inspect_response)
        try:
            page.goto(base+'/index',wait_until='networkidle')
            expect(page.locator('.mall-card').first).to_be_visible()
            assert len(page.locator('.mall-card').all())>0
            def images_loaded():
                bad=page.locator('img').evaluate_all('(xs)=>xs.filter(x=>{const r=x.getBoundingClientRect();return r.width && r.bottom>0 && r.top<innerHeight && (!x.complete || !x.naturalWidth)}).map(x=>x.src)')
                assert not bad,bad
            images_loaded()
            page.screenshot(path=str(ROOT/'docs/evidence'/f'{a.label}-home-1440.png'),full_page=False)
            checks.append('desktop catalog, branding and images under /dingping/')
            secure=page.evaluate('({secure:isSecureContext,randomUUID:typeof crypto.randomUUID,getRandomValues:typeof crypto.getRandomValues})')
            assert secure['secure'] is False,secure
            assert secure['randomUUID']=='undefined',secure
            checks.append('real insecure HTTP origin without crypto.randomUUID')
            page.goto(base+'/products/800001',wait_until='networkidle')
            expect(page.get_by_role('button',name='立即购买',exact=True)).to_be_enabled()
            images_loaded()
            page.reload(wait_until='networkidle')
            expect(page.get_by_role('button',name='立即购买',exact=True)).to_be_enabled()
            checks.append('product deep link, gallery images and reload')
            page.goto(base+'/checkout/900001',wait_until='networkidle')
            expect(page).to_have_url(re.compile('/dingping/login\\?redirect='))
            page.get_by_placeholder('请输入手机号').fill('18000000004')
            page.get_by_role('button',name='获取验证码',exact=True).click()
            expect(page.get_by_placeholder('请输入验证码')).to_have_value(re.compile('\\d{6}'))
            page.get_by_role('checkbox').check()
            page.get_by_role('button',name='登录',exact=True).click()
            expect(page.get_by_role('heading',name='确认体验订单',exact=True)).to_be_visible()
            images_loaded()
            checks.append('OTP autofill, login and return to checkout inside mount')
            token=page.evaluate('JSON.parse(localStorage.getItem("Hmdp-User")).token')
            for method_path,expected in [
                ('/api/user/code?phone=18000000001',403),
                ('/api/user/code;review?phone=18000000001',400),
                ('/api/user/;review/code?phone=18000000001',400),
                ('/api/user/code%3Breview?phone=18000000001',400),
                ('/api/user/code/?phone=18000000001',403),
            ]:
                policy_base=base.replace('dingping-preview.test','127.0.0.1') if a.local_resolver else base
                denied=context.request.post(policy_base+method_path,headers={'Authorization':token})
                assert denied.status==expected,(method_path,denied.status)
            checks.append('privileged OTP denied, including authenticated matrix/trailing/encoded paths')
            posted=[]
            def submission(route):
                payload=route.request.post_data_json
                assert re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',payload['requestKey']),payload
                posted.append(payload['requestKey'])
                if a.trade:route.continue_()
                else:route.fulfill(status=503,content_type='application/json',body=json.dumps({'success':False,'errorMsg':'Preview interception: no order written'}))
            page.route('**/dingping/api/trade/orders',submission)
            page.get_by_role('checkbox').check()
            page.get_by_role('button',name='提交订单，前往收银台',exact=True).click()
            if a.trade:
                expect(page).to_have_url(re.compile('/dingping/orders/[0-9]+$'))
                order_id=page.url.rsplit('/',1)[-1]
                expect(page.get_by_role('heading',name='待付款',exact=True)).to_be_visible()
                page.get_by_role('button',name='模拟支付失败',exact=True).click()
                expect(page.get_by_role('status')).to_contain_text('模拟支付失败')
                page.get_by_role('button',name='模拟支付成功',exact=True).click()
                expect(page.get_by_role('heading',name='待使用',exact=True)).to_be_visible()
                credential=page.locator('.mall-redemption-code').inner_text()
                assert re.fullmatch('[a-f0-9]{32}',credential)
                page.reload(wait_until='networkidle')
                expect(page.locator('.mall-redemption-code')).to_have_text(credential)
                checks.append('demo order, failed payment retry, simulated payment, persistent voucher')
                page.screenshot(path=str(ROOT/'docs/evidence'/f'{a.label}-paid-1440.png'),full_page=True)
            else:
                expect(page.locator('.mall-error')).to_contain_text('Preview interception')
            assert posted
            checks.append('HTTP UUID fallback creates valid order idempotency key')
            page.unroute('**/dingping/api/trade/orders')
            page.goto(base+'/blogEdit',wait_until='networkidle')
            page.get_by_label('上传笔记图片',exact=True).set_input_files(str(ROOT/'hmdp-vue3/public/brand/favicon-32.png'))
            uploaded=page.get_by_alt_text('已上传图片',exact=True)
            expect(uploaded).to_be_visible()
            page.wait_for_load_state('networkidle')
            assert uploaded.get_attribute('src').startswith(origin.path+'/imgs/blogs/upload/')
            images_loaded()
            with page.expect_response(lambda r:'/api/upload/blog/delete?' in r.url) as removed:
                page.get_by_role('button',name='删除图片',exact=True).click()
            assert removed.value.json()['success'],removed.value.status
            expect(uploaded).to_have_count(0)
            checks.append('temporary image upload, mount-aware preview and canonical-path deletion')
            for path in ('/discover','/shopDetail/1001','/places','/content-sources.html'):
                page.goto(base+path,wait_until='networkidle')
                images_loaded()
                assert '404' not in page.title()
            checks.append('sharing, shop detail, open places and attribution links')
            page.set_viewport_size({'width':390,'height':844})
            page.goto(base+'/index',wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            images_loaded()
            page.screenshot(path=str(ROOT/'docs/evidence'/f'{a.label}-home-390.png'),full_page=True)
            page.goto(base+'/products/800001',wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(ROOT/'docs/evidence'/f'{a.label}-product-390.png'),full_page=True)
            checks.append('390px catalog and product without horizontal overflow')
            assert not errors,errors
            assert not outside,outside
            assert not failures,failures
        except Exception:
            page.screenshot(path=str(ROOT/'docs/evidence'/f'{a.label}-failure.png'),full_page=True)
            raise
        finally:
            browser.close()
    report={'base':base,'checks':checks,'pageErrors':errors,'httpFailures':failures,'requestsOutsideMount':outside,'orderId':order_id,'tradeWrites':a.trade,'temporaryUploadDeleted':True}
    (ROOT/'docs/evidence'/f'{a.label}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
