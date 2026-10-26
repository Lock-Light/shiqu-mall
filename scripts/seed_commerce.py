"""Minimal bootstrap/test seed, not the rich editorial catalog.

Rich content is imported by import_content.py. Never downgrade existing records.
"""
import json, argparse
from pathlib import Path
from migrate_commerce import ROOT, sql as run_sql
from verify_api import login, data, BASE

THEMES = {
 'sport': ('运动','#cce7dc','#17685b','向上探索'),
 'craft': ('手作','#f4dfb1','#955632','把灵感做成作品'),
 'play': ('文娱','#dce0f5','#5b59a0','和朋友一起尽兴'),
 'rest': ('休闲','#d7e8ed','#22667c','留一点时间给自己')}
SHOP_THEMES = ['sport','sport','sport','sport','craft','craft','craft','play','play','play','craft','rest']
TYPE_IDS = {'sport':21,'craft':22,'play':23,'rest':24}

def assets():
    target=ROOT/'hmdp-vue3/public/imgs/commerce';target.mkdir(parents=True,exist_ok=True)
    for key,(category,bg,ink,caption) in THEMES.items():
        motifs={
          'sport':'<path d="M110 360 260 100 430 360M260 100 390 200 460 140 610 360" fill="none" stroke="currentColor" stroke-width="18"/><circle cx="360" cy="90" r="30" fill="#e9b949"/>',
          'craft':'<ellipse cx="360" cy="340" rx="175" ry="24" fill="currentColor" opacity=".15"/><path d="M235 170Q360 130 485 170L455 310Q360 360 265 310Z" fill="currentColor"/><ellipse cx="360" cy="170" rx="125" ry="34" fill="#f5f7fa"/><path d="M270 130Q240 60 290 30M360 120Q330 65 380 35" fill="none" stroke="currentColor" stroke-width="8"/>',
          'play':'<rect x="170" y="110" width="190" height="230" rx="24" fill="currentColor" transform="rotate(-14 260 220)"/><rect x="350" y="105" width="190" height="230" rx="24" fill="#e9b949" transform="rotate(12 430 220)"/><circle cx="435" cy="210" r="48" fill="none" stroke="currentColor" stroke-width="12"/>',
          'rest':'<path d="M180 360Q360 170 600 270" stroke="currentColor" stroke-width="20" fill="none"/><path d="M320 280Q210 100 350 70 480 140 320 280" fill="currentColor"/><circle cx="520" cy="100" r="40" fill="#e9b949"/>'}[key]
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 460"><rect width="720" height="460" fill="{bg}"/><g color="{ink}">{motifs}</g><text x="38" y="420" font-family="Microsoft YaHei,sans-serif" font-size="25" fill="{ink}">{caption}</text><text x="38" y="48" font-family="sans-serif" font-size="17" fill="{ink}">拾趣 / {category}体验 · 场景插画</text></svg>'
        (target/(key+'.svg')).write_text(svg,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true');args=parser.parse_args()
    if args.test:assert BASE in ('http://127.0.0.1:18092','http://localhost:18092'),'Test seed requires PLUS_URL port 18092'
    schema='hmdp_commerce_test' if args.test else 'hmdp_0'
    def sql(statement):return run_sql(statement,schema)
    assets()
    shops=['岩点攀岩馆','轻跃运动空间','晴场羽球馆','环线体能馆','土与手陶艺','木间工作室','青蓝染坊','慢格摄影社','棋遇桌游社','回声音乐空间','纸上艺术空间','拾光休闲空间']
    statements=[]
    for n,name in enumerate(shops):
        sid=1001+n;theme=SHOP_THEMES[n];category=THEMES[theme][0];tid=TYPE_IDS[theme]
        for legacy in (('hmdp_test_0','hmdp_test_1') if args.test else ('hmdp_0','hmdp_1')):
            statements.append(f"INSERT IGNORE INTO {legacy}.tb_shop_type(id,name,icon,sort) VALUES({tid},'{category}','/imgs/commerce/{theme}.svg',{tid})")
            statements.append(f"INSERT IGNORE INTO {legacy}.tb_shop(id,name,type_id,images,area,address,x,y,avg_price,sold,comments,score,open_hours) VALUES({sid},'{name}（虚构演示）',{tid},'/imgs/commerce/{theme}.svg','同城体验示例区','上海市示例街区体验路{n+1}号（虚构）',{121.47+n*.001},{31.23+n*.001},88,0,0,0,'10:00-21:00')")
            if args.test:
                statements.append(f"INSERT IGNORE INTO tb_shop(id,name,address) VALUES({sid},'{name}（虚构演示）','隔离测试门店')")
    titles=['攀岩新手体验','双人轻运动体验','羽毛球入门课','周末体能体验','手捏陶杯体验','木作入门课程','植物蓝染体验','城市摄影工作坊','双人桌游畅玩','音乐节奏体验','纸艺创作体验','周末轻松体验']
    for n in range(30):
        index=n%12;pid=800001+n;theme=SHOP_THEMES[index];category=THEMES[theme][0];title=titles[index]+(' · 进阶场' if n>=24 else ' · 午后场' if n>=12 else '')
        description=f'在{shops[index]}体验{titles[index]}。包含基础材料、入门讲解和现场引导，适合第一次尝试的新朋友。门店与地址均为虚构演示。'
        rules='支付成功后30天内有效。到店出示电子凭证，由所属门店核销。每份套餐一次使用完毕；具体到店安排请提前联系门店。当前仅模拟支付，不产生真实扣款。'
        statements.append(f"INSERT IGNORE INTO mall_product(id,shop_id,title,category,cover,description,rules,status) VALUES({pid},{1001+index},'{title}','{category}','/imgs/commerce/{theme}.svg','{description}','{rules}','ACTIVE')")
        for v in range(2):
            sku=900001+n*2+v;price=39+n*3+v*30;name='单人基础套餐' if v==0 else '双人同行套餐'
            statements.append(f"INSERT IGNORE INTO mall_sku(id,product_id,name,price,available,valid_days) VALUES({sku},{pid},'{name}',{price}.90,{0 if n==29 else 20},30)")
    sql(';\n'.join(statements))
    accounts={}
    for i,role in enumerate(('admin','merchantA','merchantB','buyerA','buyerB'),1):
        account=login('1800000000'+str(i));accounts[role]=account
        if str(account['user'].get('nickName','')).startswith('user_'):
            data('/user/profile','PUT',{'nickName':{'admin':'拾趣平台演示','merchantA':'岩点店员演示','merchantB':'轻跃店员演示','buyerA':'体验用户甲','buyerB':'体验用户乙'}[role]},account['token'])
        uid=int(account['user']['id'])
        if role=='admin':
            sql(f"INSERT IGNORE INTO mall_shop_member(user_id,shop_id,role) VALUES({uid},0,'ADMIN')")
            if args.test:
                for core_schema in ('hmdp_test_0','hmdp_test_1'):
                    sql(f"INSERT IGNORE INTO {core_schema}.mall_shop_member(user_id,shop_id,role) VALUES({uid},0,'ADMIN')")
        elif role.startswith('merchant'):sql(f"INSERT IGNORE INTO mall_shop_member(user_id,shop_id,role) VALUES({uid},{1001 if role=='merchantA' else 1002},'MERCHANT')")
    (ROOT/'.runtime').mkdir(exist_ok=True)
    (ROOT/('.runtime/commerce-test-accounts.json' if args.test else '.runtime/commerce-accounts.json')).write_text(json.dumps(accounts,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Demo seed ready: 12 fictional shops, 30 products, 60 SKUs. Existing data preserved.')
if __name__=='__main__':main()
