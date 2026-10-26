import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
f=json.loads((root/'.runtime/fixtures.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Shanghai')
    context.add_init_script('localStorage.setItem("Hmdp-User",'+json.dumps(json.dumps({'token':f['a']['token']}))+')')
    page=context.new_page()
    for name,path in [('profile','/InfoHtml'),('edit','/InfoEdit'),('publish','/blogEdit'),('shop','/shopDetail/1'),('orders','/InfoHtml?tab=orders'),('other','/InfoOther/'+f['originalUser'])]:
        page.goto(f['base']+path);page.wait_for_load_state('networkidle')
        print(name,page.locator('body').inner_text()[:2300])
        print('inputs',page.locator('input,textarea,select').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,type:e.type,label:e.getAttribute("aria-label"),placeholder:e.placeholder,value:e.value}))'))
        page.screenshot(path=str(root/'docs/evidence'/('recon-'+name+'.png')),full_page=True)
    browser.close()
