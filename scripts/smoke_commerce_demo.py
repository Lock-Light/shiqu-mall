"""Deployment smoke on the demo site; creates real demo orders, never resets data.

Run after isolated acceptance and deployment, using the UI Python environment.
Uses the existing seed products, not labelled acceptance fixtures.
"""
import datetime
import json
import re
import uuid
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright
from migrate_commerce import ROOT

BASE = 'http://localhost:18091'
OUT = ROOT / 'docs/evidence'
accounts = json.loads((ROOT / '.runtime/commerce-accounts.json').read_text(encoding='utf-8'))


def api(path, method='GET', body=None, actor=None):
    headers = {'Content-Type': 'application/json'}
    if actor:
        headers['Authorization'] = accounts[actor]['token']
    request = Request(BASE.replace('localhost', '127.0.0.1') + '/api' + path, method=method, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request, timeout=25) as response:
        result = json.load(response)
    assert result.get('success'), (path, result.get('errorMsg'))
    return result.get('data')


def main():
    checks, errors = [], []
    try:
        # Refresh existing demo sessions through the real local OTP endpoint.
        for account in accounts.values():
            code = api('/user/code?phone=' + account['phone'], 'POST')
            account['token'] = api('/user/login', 'POST', {'phone': account['phone'], 'code': str(code)})
        (ROOT / '.runtime/commerce-accounts.json').write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')
        catalog = api('/mall/products')
        expected = len(json.loads((ROOT / 'content/catalog.json').read_text(encoding='utf-8'))['products']) if (ROOT / 'content/catalog.json').exists() else 30
        assert int(catalog['total']) == expected, 'Demo catalog contains unexpected data'
        checks.append({'name': 'demo catalog matches editorial manifest without test fixtures', 'passed': True, 'products': expected})

        quote = api('/mall/skus/900001/quote')
        order = api('/trade/orders', 'POST', {'skuId': '900001', 'quoteVersion': quote['quoteVersion'], 'requestKey': uuid.uuid4().hex}, 'buyerA')
        oid = str(order['id'])
        api('/trade/orders/' + oid + '/mock-pay', 'POST', {'requestKey': uuid.uuid4().hex, 'outcome': 'SUCCESS'}, 'buyerA')
        paid = api('/trade/orders/' + oid, actor='buyerA')
        code = paid['redemption']['code']
        api('/merchant/redemptions/confirm', 'POST', {'code': code}, 'merchantA')
        assert api('/trade/orders/' + oid, actor='buyerA')['status'] == 'USED'
        checks.append({'name': 'deployed ordinary order, mock payment and merchant redemption', 'passed': True, 'orderId': oid})

        product = api('/mall/products/800001')
        sku = next(item for item in product['skus'] if str(item['id']) == '900002')
        if sku['sale_mode'] == 'NORMAL':
            now = datetime.datetime.now()
            api('/merchant/activities', 'POST', {'skuId': '900002', 'startsAt': (now - datetime.timedelta(minutes=1)).isoformat(timespec='minutes'), 'endsAt': (now + datetime.timedelta(days=7)).isoformat(timespec='minutes')}, 'merchantA')
        product = api('/mall/products/800001')
        sku = next(item for item in product['skus'] if str(item['id']) == '900002')
        assert sku['activity_status'] == 'ACTIVE', 'Existing activity is not active; do not reset it'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 390, 'height': 844}, timezone_id='Asia/Shanghai')
            page = context.new_page()
            page.set_default_timeout(25000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/index')
            page.evaluate('(token)=>localStorage.setItem("Hmdp-User",JSON.stringify({token}))', accounts['buyerB']['token'])
            page.goto(BASE + '/products/800001?sku=900002')
            expect(page.get_by_role('button', name='抢购限量体验', exact=True)).to_be_enabled()
            page.screenshot(path=str(OUT / 'migration-commerce-demo-product-390.png'), full_page=True)
            page.get_by_role('button', name='抢购限量体验', exact=True).click()
            expect(page).to_have_url(re.compile('/orders/[0-9]+$'))
            expect(page.get_by_role('heading', name='待付款', exact=True)).to_be_visible()
            seckill_id = page.url.rsplit('/', 1)[-1]
            page.get_by_role('button', name='取消待支付订单', exact=True).click()
            expect(page.get_by_role('heading', name='已关闭', exact=True)).to_be_visible()
            checks.append({'name': 'deployed Lua/RabbitMQ order and cancellation through browser', 'passed': True, 'orderId': seckill_id, 'activityId': str(sku['activity_id'])})
            for width in (320, 390, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 900})
                page.goto(BASE + '/index')
                page.wait_for_load_state('networkidle')
                expect(page.locator('.mall-card').first).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert '集成验收' not in page.locator('body').inner_text()
                page.screenshot(path=str(OUT / f'migration-commerce-demo-home-{width}.png'), full_page=True)
            assert not errors, errors
            checks.append({'name': 'demo pages at 320/390/768/1440 without test fixtures or pageerrors', 'passed': True})
            context.close()
            browser.close()
    except Exception as error:
        checks.append({'name': 'deployment smoke', 'passed': False, 'error': str(error)})
    report = {'generated': datetime.datetime.now().isoformat(), 'base': BASE, 'note': 'Real demo orders retained; no reset. Not added to isolated acceptance counts.', 'checks': checks, 'pageerrors': errors}
    (OUT / 'migration-commerce-demo-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(not check['passed'] for check in checks))


if __name__ == '__main__':
    raise SystemExit(main())
