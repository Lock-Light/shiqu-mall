"""Rendered-browser acceptance. Run verify_api.py first for isolated fixtures."""
import datetime, json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from verify_api import call, data

ROOT=Path(__file__).resolve().parents[1]
F=json.loads((ROOT/'.runtime/fixtures.json').read_text(encoding='utf-8'))
BASE=F['base'];OUT=ROOT/'docs/evidence';OUT.mkdir(parents=True,exist_ok=True)
assert BASE in ('http://127.0.0.1:18092','http://localhost:18092'),'Use isolated legacy fixtures'
import verify_api as api_module
api_module.BASE=BASE
REPORT_NAME='migration-legacy-ui-commerce.json'
RESULTS=[];ERRORS=[];SELECTED=None
sys.stdout.reconfigure(encoding='utf-8')

def goto(page,path):
    page.goto(BASE+path);page.wait_for_load_state('networkidle')

def record(name,fn,page):
    if SELECTED is not None and name not in SELECTED:return
    RESULTS[:]=[r for r in RESULTS if r['name']!=name]
    start=time.monotonic()
    try:
        detail=fn()
        RESULTS.append({'name':name,'passed':True,'seconds':round(time.monotonic()-start,2),'detail':detail})
        print('PASS',name,detail or '',flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        RESULTS.append({'name':name,'passed':False,'error':str(e)})
        print('FAIL',name,str(e),flush=True)
        page.screenshot(path=str(OUT/('migration-failed-'+str(len(RESULTS))+'.png')))

def no_overflow(page):
    return page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')

def logged(browser,key):
    context=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai')
    page=context.new_page();page.set_default_timeout(12000)
    page.on('pageerror',lambda e:ERRORS.append(str(e)))
    goto(page,'/index')
    page.evaluate('(v)=>localStorage.setItem("Hmdp-User",JSON.stringify({token:v}))',F[key]['token'])
    goto(page,'/InfoHtml')
    return context,page

def main():
    global SELECTED
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--retry-failed',action='store_true');args=parser.parse_args()
    if args.retry_failed:
        previous=json.loads((OUT/REPORT_NAME).read_text(encoding='utf-8'))
        assert previous['fixtureRun']==F['run'],'retry requires the same fixture run'
        RESULTS.extend(previous['checks']);SELECTED={r['name'] for r in RESULTS if not r['passed']}
        if not SELECTED:return 0
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        anon=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai')
        page=anon.new_page();page.set_default_timeout(12000)
        page.on('pageerror',lambda e:ERRORS.append(str(e)))
        def original():
            goto(page,'/blogDetail/'+F['originalBlog']['id'])
            content=page.locator('.blog-content').inner_text()
            assert '<br' not in content and '\\n' not in content and content.count('\n')>20
            expect(page.get_by_text(F['originalBlog']['title'],exact=True)).to_be_visible()
            assert page.locator('.blog-gallery img').first.evaluate('(i)=>i.complete&&i.naturalWidth>0')
            page.screenshot(path=str(OUT/'migration-original-blog-mobile.png'),full_page=True)
            return {'realOriginalBlog':F['originalBlog']['id'],'renderedLines':content.count('\n')+1}
        record('original note text, images and safe line breaks',original,page)
        def voucher_rules():
            goto(page,'/shopDetail/1')
            voucher=page.locator('.voucher').filter(has_text='验收'+F['run']+'秒杀')
            expect(voucher).to_have_count(1)
            expect(voucher.locator('.voucher-price')).to_contain_text('50.00')
            voucher.get_by_role('button',name='使用规则',exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible()
            text=page.locator('.voucher-rules').inner_text()
            assert text=='仅限堂食\n每桌限用一张\n不与其他优惠同享',repr(text)
            page.screenshot(path=str(OUT/'migration-voucher-rules-mobile.png'))
            page.get_by_role('button',name='知道了').click()
            expect(page.locator('.voucher').filter(has_text='验收'+F['run']+'预告').get_by_role('button',name='尚未开始',exact=True)).to_be_disabled()
            expect(page.locator('.voucher').filter(has_text='验收'+F['run']+'已结束').get_by_role('button',name='已结束',exact=True)).to_be_disabled()
        record('voucher yuan amount, escaped rules and disabled activity states',voucher_rules,page)
        def login():
            goto(page,'/InfoEdit');expect(page).to_have_url(__import__('re').compile('/login\\?redirect='))
            page.get_by_role('button',name='登录',exact=True).click()
            expect(page.locator('.inline-error')).to_contain_text('手机号')
            page.get_by_placeholder('请输入手机号').fill(F['a']['phone'])
            page.get_by_role('button',name='获取验证码',exact=True).click()
            expect(page.get_by_placeholder('请输入验证码')).to_have_value(__import__('re').compile('\\d{6}'))
            expect(page.get_by_role('button',name=__import__('re').compile('秒后重发'))).to_be_disabled()
            page.get_by_role('button',name='登录',exact=True).click();expect(page.locator('.inline-error')).to_contain_text('勾选')
            page.get_by_role('checkbox').check()
            page.get_by_role('button',name='登录',exact=True).click()
            expect(page).to_have_url(BASE+'/InfoEdit')
            expect(page.get_by_placeholder('请输入昵称')).to_have_value('验收作者'+F['run'])
            return 'real OTP form → original protected destination'
        record('login validation, real OTP, countdown and protected return',login,page)
        ca,a=logged(browser,'a');cb,b=logged(browser,'b')
        def own_paging():
            expect(a.locator('.blog-card')).to_have_count(10)
            a.get_by_role('button',name='加载更多',exact=True).click()
            expect(a.locator('.blog-card')).to_have_count(12)
            ids=a.locator('.blog-card>a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))')
            assert len(set(ids))==12
            a.get_by_role('tab',name='粉丝',exact=True).click();expect(a.locator('.person')).to_have_count(1)
            a.get_by_role('tab',name='关注的人',exact=True).click();expect(a.get_by_text('暂无内容',exact=True)).to_be_visible()
            goto(b,'/InfoHtml?tab=feed')
            expect(b.locator('.blog-card')).to_have_count(2)
            for total in (4,6,8,10,12):
                b.get_by_role('button',name='加载更多',exact=True).click();expect(b.locator('.blog-card')).to_have_count(total)
            b.get_by_role('button',name='加载更多',exact=True).click();expect(b.get_by_text('已经到底了',exact=True)).to_be_visible()
            ids=b.locator('.blog-card>a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))');assert len(set(ids))==12
            return 'own notes 10+2; equal-score Feed 2×6, no duplicates'
        record('profile tabs, own note pagination and Feed cursor',own_paging,a)
        icon=ROOT/'hmdp-vue3/public/imgs/icons/default-icon.png'
        def profile():
            goto(a,'/InfoEdit')
            a.get_by_label('上传头像').set_input_files(str(icon))
            expect(a.locator('.avatar-row img')).to_have_attribute('src',__import__('re').compile('/imgs/blogs/upload/'))
            a.get_by_placeholder('请输入昵称').fill('页面验收'+F['run'])
            a.get_by_placeholder('介绍一下自己').fill('Vue3 页面保存\n第二行介绍')
            a.get_by_placeholder('请输入城市').fill('上海')
            a.get_by_label('性别').select_option('true');a.get_by_label('生日').fill('2001-02-03')
            a.get_by_role('button',name='保存资料',exact=True).click()
            expect(a).to_have_url(BASE+'/InfoHtml');expect(a.get_by_role('heading',name='页面验收'+F['run'])).to_be_visible()
            a.reload();expect(a.get_by_text('上海',exact=True)).to_be_visible()
            avatar=a.locator('.profile>img').get_attribute('src')
            assert '/blogs/upload/'+str(F['a']['user']['id'])+'/' in avatar
            assert a.locator('.profile>img').evaluate('(i)=>i.complete&&i.naturalWidth>0')
            assert not call('/upload/blog/delete?'+__import__('urllib.parse',fromlist=['urlencode']).urlencode({'name':avatar}),token=F['b']['token'],ok=False)['success']
            goto(a,'/InfoEdit');expect(a.get_by_label('生日')).to_have_value('2001-02-03');expect(a.get_by_label('性别')).to_have_value('true')
            return {'savedAvatar':True,'crossUserDeleteRejected':True}
        record('avatar upload, profile persistence and upload ownership',profile,a)
        def publish():
            goto(a,'/blogEdit');a.get_by_role('button',name='发布笔记',exact=True).click();expect(a.get_by_role('alert')).to_contain_text('标题')
            title='浏览器发布'+F['run']
            a.get_by_placeholder('填写笔记标题').fill(title);a.get_by_placeholder('分享你的探店体验').fill('第一行<br/>第二行\\n第三行\n<img src=x onerror="window.__xss=1">')
            a.get_by_label('上传笔记图片').set_input_files({'name':'wrong.txt','mimeType':'text/plain','buffer':b'bad'})
            expect(a.get_by_role('alert')).to_contain_text('图片')
            a.get_by_label('上传笔记图片').set_input_files(str(icon));expect(a.locator('.upload-item')).to_have_count(1)
            a.get_by_role('button',name='删除图片',exact=True).click();expect(a.locator('.upload-item')).to_have_count(0)
            a.get_by_label('上传笔记图片').set_input_files(str(icon));expect(a.locator('.upload-item')).to_have_count(1)
            a.get_by_role('button',name=__import__('re').compile('关联商户')).click()
            expect(a.get_by_role('dialog')).to_be_visible()
            a.get_by_placeholder('搜索商户名称或地点').fill('103');a.get_by_role('dialog').get_by_role('button',name='搜索',exact=True).click()
            a.get_by_role('dialog').get_by_role('button',name=__import__('re').compile('103茶餐厅')).click()
            expect(a.get_by_role('dialog')).not_to_be_visible()
            a.reload();expect(a.get_by_placeholder('填写笔记标题')).to_have_value(title);expect(a.locator('.choose-shop')).to_contain_text('103茶餐厅')
            a.get_by_role('button',name='发布笔记',exact=True).click();expect(a).to_have_url(__import__('re').compile('/blogDetail/[0-9]+'))
            expect(a.get_by_role('heading',name=title)).to_be_visible();expect(a.locator('.blog-content')).to_contain_text('第一行\n第二行\n第三行')
            assert a.locator('.blog-content img').count()==0 and not a.evaluate('window.__xss')
            F['uiNote']=a.url.rsplit('/',1)[-1]
            a.screenshot(path=str(OUT/'migration-published-note-mobile.png'),full_page=True)
            return {'newLongId':F['uiNote'],'draftRestored':True,'renderedMarkupSafe':True}
        record('publish validation, upload/delete/reselect, shop picker, draft and actual detail',publish,a)
        def social():
            goto(b,'/blogDetail/'+F.get('uiNote',F['notes'][-1]))
            b.get_by_role('button',name='点赞',exact=True).click();expect(b.get_by_role('button',name='取消点赞',exact=True)).to_be_visible()
            b.get_by_role('button',name='取消点赞',exact=True).click();expect(b.get_by_role('button',name='点赞',exact=True)).to_be_visible()
            goto(b,'/InfoOther/'+F['originalUser']);b.get_by_role('button',name='关注作者',exact=True).click();expect(b.get_by_role('button',name='取消关注',exact=True)).to_be_visible()
            b.reload();expect(b.get_by_role('button',name='取消关注',exact=True)).to_be_visible()
            b.get_by_role('button',name='取消关注',exact=True).click();expect(b.get_by_role('button',name='关注作者',exact=True)).to_be_visible()
            b.get_by_role('button',name='共同关注',exact=True).click();expect(b.get_by_text('暂无内容',exact=True)).to_be_visible()
        record('rendered like/unlike, follow/unfollow persistence and common follows',social,b)
        def coupons():
            goto(b,'/shopDetail/1');v=b.locator('.voucher').filter(has_text='验收'+F['run']+'秒杀')
            v.get_by_role('button',name='限时抢购',exact=True).click()
            expect(v.get_by_role('button',name='已领取',exact=True)).to_be_visible(timeout=25000)
            expect(v.locator('.coupon-message')).to_contain_text('落单成功')
            v.get_by_role('button',name='取消领取',exact=True).click();b.get_by_role('button',name='确认取消',exact=True).click()
            expect(v.get_by_role('button',name='限时抢购',exact=True)).to_be_enabled()
            s=b.locator('.voucher').filter(has_text='验收'+F['run']+'订阅')
            s.get_by_role('button',name='订阅到券提醒',exact=True).click();expect(s.get_by_role('button',name='取消订阅',exact=True)).to_be_visible()
            s.get_by_role('button',name='取消订阅',exact=True).click();expect(s.get_by_role('button',name='订阅到券提醒',exact=True)).to_be_visible()
            v.get_by_role('link',name='查看我的订单',exact=True).click();expect(b.get_by_role('tab',name='历史券订单')).to_have_attribute('aria-selected','true')
            expect(b.locator('.order').filter(has_text='验收'+F['run']+'秒杀')).to_contain_text('已取消')
            b.screenshot(path=str(OUT/'migration-orders-mobile.png'))
            return 'button → access token → real RabbitMQ commit → cancel → own order status 2'
        record('real UI purchase/cancel, subscriptions and order state',coupons,b)
        def shops():
            goto(page,'/shopList?type=1');expect(page.locator('.shop-card')).to_have_count(5)
            page.get_by_role('button',name='加载更多',exact=True).click();expect(page.locator('.shop-card')).to_have_count(9)
            page.get_by_role('button',name='评分',exact=True).click();expect(page).to_have_url(__import__('re').compile('sort=score'))
            expect(page.locator('.shop-card')).to_have_count(5)
            page.get_by_label('搜索商户').fill('不可能存在的商户xyz');page.get_by_role('button',name='搜索',exact=True).click()
            expect(page.get_by_text('没有找到商户，请换个分类、关键词或位置',exact=True)).to_be_visible()
            goto(page,'/shopList?type=1');page.get_by_role('button',name='使用我的位置',exact=True).click()
            expect(page.get_by_text('未获得定位，继续使用演示位置',exact=True)).to_be_visible(timeout=12000)
        record('shop pagination, sorting, empty search and denied geolocation',shops,page)
        def retry():
            def fail(route): route.fulfill(status=503,content_type='application/json',body='{}')
            page.route('**/api/blog/hot?*',fail);goto(page,'/discover?source=legacy')
            expect(page.get_by_role('button',name='重试',exact=True)).to_be_visible()
            page.unroute('**/api/blog/hot?*',fail);page.get_by_role('button',name='重试',exact=True).click()
            expect(page.locator('.blog-card').first).to_be_visible()
            for path,text in [('/shopDetail/bad','商户不存在'),('/shopDetail/99999999','店铺不存在'),('/blogDetail/99999999','笔记不存在'),('/InfoOther/99999999','用户不存在'),('/does-not-exist','页面不存在')]:
                goto(page,path);expect(page.locator('body')).to_contain_text(text)
            page.route('**://qcloud.dpfile.com/**',lambda route:route.abort())
            goto(page,'/shopDetail/1');expect(page.locator('.image-error').first).to_be_visible()
            page.unroute('**://qcloud.dpfile.com/**')
            return '503 injected once; successful retry and real missing entities'
        record('network error/retry, invalid routes and remote image fallback',retry,page)
        def responsive():
            # Cover both HTTP and HTTPS source URLs before redirects; layout must
            # remain usable with the upstream legacy photo host unavailable.
            page.route('**://qcloud.dpfile.com/**',lambda route:route.abort())
            measurements=[]
            for width in (320,390,1440):
                page.set_viewport_size({'width':width,'height':900})
                for path in ('/index','/shopDetail/1','/blogDetail/'+F['originalBlog']['id'],'/login','/shopList?type=1'):
                    goto(page,path);v=no_overflow(page);assert v['scroll']<=v['width'],(path,v)
                    measurements.append({'width':width,'path':path,'scroll':v['scroll']})
                page.screenshot(path=str(OUT/f'migration-shops-{width}.png'))
            page.unroute('**://qcloud.dpfile.com/**')
            return measurements
        record('320/390/1440 viewport layout, five principal pages each',responsive,page)
        def expiry():
            a.evaluate('localStorage.setItem("Hmdp-User",JSON.stringify({token:"expired-demo-token"}))')
            goto(a,'/InfoEdit');expect(a).to_have_url(__import__('re').compile('/login\\?redirect='))
            assert json.loads(a.evaluate('localStorage.getItem("Hmdp-User")'))['token']==''
            # The original context completed the real login test. Use a new,
            # actually anonymous context for this independent authorization check.
            fresh=browser.new_context(timezone_id='Asia/Shanghai')
            try:
                fresh_page=fresh.new_page();goto(fresh_page,'/InfoHtml');expect(fresh_page).to_have_url(__import__('re').compile('/login'))
            finally:fresh.close()
        record('expired token clears state and anonymous protected route redirects',expiry,a)
        def logout():
            goto(b,'/InfoHtml');b.get_by_role('button',name='退出登录',exact=True).click();expect(b).to_have_url(BASE+'/index')
            assert call('/user/me',token=F['b']['token'],ok=False).get('http')==401
            goto(b,'/InfoHtml');expect(b).to_have_url(__import__('re').compile('/login'))
        record('browser logout revokes actual server session',logout,b)
        record('no unhandled browser exceptions',lambda: (_ for _ in ()).throw(AssertionError(ERRORS)) if ERRORS else '0 pageerror events across all contexts',page)
        browser.close()
    report={'time':datetime.datetime.now().isoformat(),'base':BASE,'fixtureRun':F['run'],'checks':RESULTS,'pageErrors':ERRORS,'passed':all(r['passed'] for r in RESULTS) and not ERRORS,'retestedFailedChecks':sorted(SELECTED) if SELECTED is not None else []}
    (OUT/REPORT_NAME).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main())
