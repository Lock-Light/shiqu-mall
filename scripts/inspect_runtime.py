"""Read-only reconnaissance before acceptance selectors are chosen."""
import json, sys
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
out = root / 'docs/evidence'
out.mkdir(parents=True, exist_ok=True)
base='http://localhost:18091'
def api(path):
    return json.load(urlopen(base+'/api'+path))
hot=api('/blog/hot?current=1')['data']
print('HOT', json.dumps(hot[:1],ensure_ascii=False))
print('VOUCHERS', json.dumps(api('/voucher/list/1'),ensure_ascii=False))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    for name,path in [('home','/index'),('shop','/shopDetail/1'),('blog','/blogDetail/'+str(hot[0]['id'])),('login','/login'),('shops','/shopList?type=1')]:
        page.goto(base+path)
        page.wait_for_load_state('networkidle')
        print(name, page.locator('body').inner_text()[:5000])
        print('buttons',page.get_by_role('button').all_text_contents())
        print('images',page.locator('img').evaluate_all('(imgs)=>imgs.map(i=>({src:i.getAttribute("src"),ok:i.complete&&i.naturalWidth>0}))'))
        page.screenshot(path=str(out/('recon-'+name+'.png')),full_page=True)
    print('ERRORS',errors)
    browser.close()
