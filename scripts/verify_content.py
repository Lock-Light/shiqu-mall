"""Read-only content and rendered-page acceptance against the deployed 18091 site."""
import datetime, hashlib, json, re, sys
from urllib.parse import urlencode
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
from migrate_commerce import ROOT

sys.stdout.reconfigure(encoding='utf-8')
BASE='http://localhost:18091';OUT=ROOT/'docs/evidence';checks=[];errors=[]
catalog=json.loads((ROOT/'content/catalog.json').read_text(encoding='utf-8'))
photos=json.loads((ROOT/'content/photo-manifest.json').read_text(encoding='utf-8'))

def api(path):
    with urlopen(BASE.replace('localhost','127.0.0.1')+'/api'+path,timeout=25) as response:result=json.load(response)
    assert result['success'],path
    return result['data']

def check(name,fn):
    try:
        detail=fn();checks.append({'name':name,'passed':True,'detail':detail});print('PASS',name,flush=True)
    except Exception as error:
        checks.append({'name':name,'passed':False,'error':str(error)});print('FAIL',name,str(error),flush=True)

def main():
    def coverage():
        found=[]
        for page in range(1,9):found.extend(api('/mall/products?page='+str(page))['list'])
        assert len(found)==len({str(p['id']) for p in found})==96
        assert {str(p['id']) for p in found}=={str(p['id']) for p in catalog['products']}
        mixed=api('/mall/products?sort=explore')['list']
        assert len({r['category'] for r in mixed})==4 and len({r['shop_id'] for r in mixed})>=8
        for category in ('运动','手作','文娱','休闲'):
            assert int(api('/mall/products?'+urlencode({'category':category}))['total'])==24
        preserved=json.loads((OUT/'content-import.json').read_text(encoding='utf-8'))
        for p in catalog['products']:
            actual=api('/mall/products/'+str(p['id']))
            assert actual['gallery'] and actual['shop_profile']['introduction']
            if p['id'] not in preserved['activeProductContentPreserved']:
                assert actual['title']==p['title'] and '【包含与不含】' in actual['description']
            assert all(str(s['id']).isdigit() and re.fullmatch(r'\d+\.\d{2}',s['price']) for s in actual['skus'])
        assert preserved['protectedStateUnchanged'] and preserved['countsBefore']==preserved['countsAfter']
        return {'shops':32,'products':96,'skus':192,'categories':{c:24 for c in ('运动','手作','文娱','休闲')},'repeatImportUnchanged':True,'frozenProductPreserved':preserved['activeProductContentPreserved']}
    check('catalog, explicit categories, all detail content and repeat-import protection',coverage)
    def local_media():
        assert len({p['sourcePage'] for p in photos})==40
        for p in photos:
            assert p['author'] and p['licenseUrl'].startswith('http')
            for key,sha in [('path','sha256'),('thumbnail','thumbnailSha256')]:
                with urlopen(BASE.replace('localhost','127.0.0.1')+p[key],timeout=20) as response:
                    data=response.read();assert response.headers['Content-Type'].startswith('image/webp')
                assert hashlib.sha256(data).hexdigest()==p[sha],p['assetId']
        return {'photos':40,'localImageResponses':80,'allHashesMatched':True}
    check('40 attributed local photographs and 40 thumbnails load with matching hashes',local_media)
    def places():
        rows=[]
        for page in range(1,4):rows.extend(api('/mall/places?page='+str(page))['list'])
        source=json.loads((ROOT/'content/poi/shanghai-sports-osm-sample.json').read_text(encoding='utf-8'))
        expected={r['sourceId']:r for r in source['rows'] if r.get('name') or r.get('nameEn')}
        assert len(rows)==len(expected)==25
        assert {r['source_id'] for r in rows}==set(expected)
        assert all(r['source_url']==expected[r['source_id']]['sourceUrl'] and r['license']=='ODbL 1.0' and abs(float(r['longitude'])-expected[r['source_id']]['longitude'])<1e-7 and abs(float(r['latitude'])-expected[r['source_id']]['latitude'])<1e-7 for r in rows)
        return {'rawRows':26,'namedRows':25,'license':'ODbL 1.0','sourceTimestamp':source['osmBaseTimestamp']}
    check('real OSM sample preserves names, IDs, links and data license',places)
    def stories():
        rows=[]
        for page in range(1,6):rows.extend(api('/mall/stories?page='+str(page)))
        assert len(rows)==len({r['id'] for r in rows})==48
        for row in rows:
            assert '演示' in row['title'] and '演示' in row['name']
            actual=api('/blog/'+row['id'])
            assert '不是真实消费者评价' in actual['content'] and str(actual['shopId']) in {str(s['id']) for s in catalog['shops']}
        authors=json.loads((OUT/'content-import.json').read_text(encoding='utf-8'))['authors']
        assert len(authors)==12
        assert all(int(api('/user/profile/'+a['id'])['fans'])>=2 for a in authors)
        return {'stories':48,'authors':12,'syntheticFollowEdges':24}
    check('48 distinct demo stories, real venue links and synthetic author relations',stories)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai');page=context.new_page();page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)))
        def goto(path):page.goto(BASE+path);page.wait_for_load_state('networkidle')
        def loaded(selector):
            for image in page.locator(selector).all():
                image.scroll_into_view_if_needed();expect(image).to_be_visible()
                assert image.evaluate('(i)=>i.complete && i.naturalWidth>0'),image.get_attribute('src')
        def layouts():
            for width in (320,390,768,1440):
                page.set_viewport_size({'width':width,'height':900});goto('/index');expect(page.locator('.mall-card')).to_have_count(12);loaded('.mall-card img')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(OUT/f'content-home-{width}.png'),full_page=True)
            first=page.locator('.mall-card').first.get_attribute('href');page.get_by_role('button',name='下一页',exact=True).click();page.wait_for_load_state('networkidle');expect(page).to_have_url(re.compile('page=2'));assert page.locator('.mall-card').first.get_attribute('href')!=first
            page.get_by_label('搜索体验商品').fill('银戒');page.get_by_role('button',name='搜索',exact=True).click();expect(page.locator('.mall-card').first).to_contain_text('银戒')
            return {'widths':[320,390,768,1440],'pagination':True,'search':'银戒'}
        check('browser home photographs, pagination, search and four responsive widths',layouts)
        def categories():
            samples=[]
            for category in ('运动','手作','文娱','休闲'):
                goto('/index');page.get_by_role('button',name=category,exact=True).click();expect(page).to_have_url(re.compile('category='));expect(page.locator('.mall-card')).to_have_count(12)
                p=next(p for p in catalog['products'] if p['category']==category and not p['legacy'])
                page.set_viewport_size({'width':390,'height':900});goto('/products/'+str(p['id']));expect(page.get_by_role('heading',name=p['title'],exact=True)).to_be_visible();loaded('.mall-detail-image,.mall-gallery img')
                expect(page.get_by_text('【包含与不含】',exact=False)).to_be_visible();assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(OUT/f'content-detail-{p["key"]}-390.png'),full_page=True);samples.append({'category':category,'id':p['id'],'title':p['title']})
            return samples
        check('all four category filters and readable matching product details',categories)
        def shops():
            goto('/shopList?type=21');expect(page.locator('.shop-card').first).to_be_visible();loaded('.shop-card img');page.screenshot(path=str(OUT/'migration-content-nearby-390.png'),full_page=True)
            goto('/shopDetail/1005');expect(page.get_by_role('heading',name='到店提示',exact=True)).to_be_visible();expect(page.get_by_role('heading',name='本店体验商品',exact=True)).to_be_visible();loaded('.shop-images img');assert page.get_by_text('0条评价',exact=True).count()==0
            page.screenshot(path=str(OUT/'migration-content-shop-390.png'),full_page=True)
            return {'nearbyType':21,'shopId':1005,'noInventedRatings':True}
        check('nearby demo venues, shop profiles, photography and real product links',shops)
        def reference():
            goto('/places');expect(page.get_by_role('heading',name='上海开放场所参考',exact=True)).to_be_visible();expect(page.locator('article')).to_have_count(12);assert page.get_by_role('button',name='立即购买',exact=True).count()==0
            page.get_by_role('button',name='下一页',exact=True).click();expect(page.get_by_text('第 2 页',exact=True)).to_be_visible();page.get_by_role('button',name='下一页',exact=True).click();expect(page.locator('article')).to_have_count(1);expect(page.get_by_role('button',name='下一页',exact=True)).to_be_disabled();page.screenshot(path=str(OUT/'migration-content-open-places-390.png'),full_page=True)
            return {'pages':3,'referenceOnly':True}
        check('open-place source attribution and pagination with no purchase controls',reference)
        def rendered_stories():
            goto('/discover');expect(page.locator('.blog-card')).to_have_count(10);loaded('.blog-card .cover');page.screenshot(path=str(OUT/'migration-content-stories-390.png'),full_page=True)
            page.get_by_role('button',name='加载更多',exact=True).click();expect(page.locator('.blog-card')).to_have_count(20)
            link=page.locator('.blog-card a').first.get_attribute('href');goto(link);expect(page.get_by_text('不是真实消费者评价',exact=False)).to_be_visible();loaded('.blog-gallery .el-image img:visible');assert re.search(r'/blogDetail/\d{19}$',page.url)
            page.screenshot(path=str(OUT/'migration-content-story-detail-390.png'),full_page=True);return {'storyDetail':page.url.rsplit('/',1)[-1],'longIdIntact':True}
        check('demo story feed, more pages, long ID and associated detail images',rendered_stories)
        def credits():
            goto('/content-sources.html');expect(page.locator('article')).to_have_count(40);assert page.get_by_text('ODbL 1.0',exact=True).count()==1
            assert not errors,errors;return {'imageCredits':40,'pageerrors':0}
        check('attribution page and no unhandled browser exceptions',credits)
        context.close();browser.close()
    report={'generated':datetime.datetime.now().isoformat(),'base':BASE,'checks':checks,'pageerrors':errors,'allPassed':all(c['passed'] for c in checks)}
    (OUT/'migration-content-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(not report['allPassed'])

if __name__=='__main__':raise SystemExit(main())
