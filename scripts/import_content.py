"""Versioned editorial import. Existing order snapshots and SKU state are immutable.

Only the known seed IDs and this batch's registered records may be updated.
Real OSM places live in a separate reference table, never in merchant inventory.
"""
import argparse, datetime, hashlib, html, json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'content'))
from experience_catalog import SHOPS, AREAS
from migrate_commerce import ROOT, sql
from verify_api import login, data, redis

BATCH='experience-content-20261024-v1'
TYPES={'运动':21,'手作':22,'文娱':23,'休闲':24}
ALT={'climb':'climb2','pottery':'pottery2','wood':'wood2','flower':'flower2','coffee':'coffee2','tea':'tea2','board':'board2','garden':'garden2'}

def q(value):
    if value is None:return 'NULL'
    if isinstance(value,(int,float)):return str(value)
    return "CONVERT(0x"+str(value).encode('utf-8').hex()+" USING utf8mb4)" if str(value) else "''"

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def redis_batch(commands):
    # RESP pipeline is bounded to this content batch; never flushes unrelated keys.
    payload=b''
    for command in commands:
        parts=[str(part).encode('utf-8') for part in command]
        payload+=b'*'+str(len(parts)).encode()+b'\r\n'+b''.join(b'$'+str(len(part)).encode()+b'\r\n'+part+b'\r\n' for part in parts)
    output=subprocess.check_output(['docker','compose','exec','-T','redis','redis-cli','--no-auth-warning','-a','plus-local','--pipe'],input=payload,cwd=ROOT).decode()
    assert 'errors: 0' in output,output

def snapshot():
    parts={}
    for table in ('mall_trade_order','mall_payment_attempt','mall_redemption','mall_order_event','mall_stock_movement'):
        parts[table]=hashlib.sha256(sql('SELECT * FROM '+table+' ORDER BY id').encode()).hexdigest()
    # Fixed existing IDs only: newly added SKUs are expected; existing SKU fields must not change.
    parts['oldSkus']=hashlib.sha256(sql('SELECT * FROM mall_sku WHERE id BETWEEN 900001 AND 900060 ORDER BY id').encode()).hexdigest()
    parts['activities']=hashlib.sha256(sql('SELECT * FROM mall_seckill_activity ORDER BY id').encode()).hexdigest()
    return parts

def counts():
    rows=sql("SELECT 'shops',COUNT(*) FROM mall_shop_profile UNION ALL SELECT 'products',COUNT(*) FROM mall_product UNION ALL SELECT 'skus',COUNT(*) FROM mall_sku UNION ALL SELECT 'stories',COUNT(*) FROM mall_demo_record WHERE kind='story' UNION ALL SELECT 'referencePlaces',COUNT(*) FROM mall_reference_place").splitlines()
    return {line.split('\t')[0]:int(line.split('\t')[1]) for line in rows}

def compile_catalog():
    assets={a['assetId']:a for a in json.loads((ROOT/'content/photo-manifest.json').read_text(encoding='utf-8'))}
    shops=[];products=[];extra=0
    for s in SHOPS:
        sid,key,name,category,area,hours,intro,audience,tips,materials,experiences=s
        x,y,district,transit=AREAS[area]
        # Small deterministic offsets stay within the named business area; not a navigable real venue.
        offset=(sid%7-3)*0.00025
        media=[key]+([ALT[key]] if key in ALT else [])
        shops.append({'id':sid,'key':key,'name':name+'（虚构演示）','category':category,'typeId':TYPES[category],'area':area,'x':round(x+offset,6),'y':round(y-offset,6),'address':f'上海市{district}{area}片区·体验单元{sid}（虚构地址）','hours':hours,'introduction':intro,'audience':audience,'arrivalTips':tips+' '+transit+'。坐标仅供商圈演示，不对应真实经营地址。','photos':media})
        old=[800001+n for n in range(30) if 1001+n%12==sid]
        for i,(title,minutes,price,outcome,flow) in enumerate(experiences):
            if i<len(old):pid=old[i];legacy=True
            else:extra+=1;pid=820000+extra;legacy=False
            source=[assets[k] for k in media]
            description=f'【体验目标】\n{outcome}\n\n【约{minutes}分钟的体验流程】\n{flow.replace("→", " → ")}。根据参与者节奏保留休息时间。\n\n【包含与不含】\n{materials}\n\n【适合人群与条件】\n{audience}\n\n【到店准备】\n{tips}\n\n【演示说明】\n商品与门店为虚构设计，照片是开放许可题材配图，不代表本店实景。'
            rules=f'套餐一次使用完毕；单人规格供1人，双人规格供2人共同到店，不可拆次。支付成功后30天内有效，需提前联系门店确认场次；平台当前不提供预约排期。\n{materials}\n{tips}\n未付款可取消，已付款本演示版本暂无退款入口，请先确认条件。仅模拟支付，不产生真实扣款。'
            products.append({'id':pid,'shopId':sid,'title':title,'category':category,'minutes':minutes,'price':price,'outcome':outcome,'flow':flow,'description':description,'rules':rules,'cover':source[i%len(source)]['thumbnail'],'photos':media,'legacy':legacy,'key':key})
    stories=[]
    # Every venue has one story, 16 venues have a second distinct topic; all tagged editorial demo.
    selections=[(s,0) for s in shops]+[(s,1) for s in shops[:16]]
    for i,(shop,variant) in enumerate(selections):
        p=[p for p in products if p['shopId']==shop['id']][variant]
        body=f'【原创演示分享·虚构体验记录】\n这篇内容用于演示作者、门店关联和图片展示，不是真实消费者评价。\n\n这次给自己定的小目标是：{p["outcome"]}\n我选的是「{p["title"]}」，约{p["minutes"]}分钟。流程里最想认真体验的是：{p["flow"].split("→")[variant+1]}。把结果做出来之前，先看清楚每一步为什么这样安排。\n\n出门前的小清单：{shop["arrivalTips"]}\n{shop["name"].replace("（虚构演示）","")}的体验设定是：{shop["introduction"]}\n\n给同样准备第一次尝试的人：{shop["audience"]} 先看商品页的包含与不含，再确认个人条件，不用一次就追求熟练。\n\n配图为{assets[p["key"]]["caption"]}题材的开放许可照片，不是该虚构门店实景；作者和许可见素材来源页。'
        stories.append({'id':str(2180000000000000001+i),'shopId':shop['id'],'authorIndex':i%12,'title':('第一次尝试：' if not variant else '周末再探索：')+p['title']+'｜演示','content':body,'images':[assets[k]['path'] for k in p['photos']],'createdAt':(datetime.datetime(2026,10,24,10,0)-datetime.timedelta(hours=i*7)).isoformat(sep=' ')})
    catalog={'batch':BATCH,'fictional':True,'shops':shops,'products':products,'stories':stories}
    (ROOT/'content/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    return catalog,assets

def record(kind,id,value):
    return f'INSERT INTO mall_demo_record(kind,entity_id,batch,content_hash) VALUES({q(kind)},{q(id)},{q(BATCH)},{q(digest(value))}) ON DUPLICATE KEY UPDATE content_hash=VALUES(content_hash),batch=VALUES(batch);'

def attribution(assets):
    rows=[]
    for a in assets.values():
        e=lambda value:html.escape(str(value),quote=True)
        rows.append(f'<article id="{e(a["assetId"])}"><img loading="lazy" src="{e(a["thumbnail"])}" alt="{e(a["caption"])}"><h2>{e(a["caption"])}</h2><p>{e(a["title"])} — {e(a["author"])}</p><a href="{e(a["sourcePage"])}">原始文件说明页</a> · <a href="{e(a["licenseUrl"])}">{e(a["license"])}</a><p>{e(a["modifications"])}</p><p>本地文件：{e(a["path"])}</p></article>')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>照片与开放数据来源 - 拾趣</title><style>body{font:16px/1.7 system-ui;margin:32px auto;padding:0 18px;max-width:1000px;color:#17212b}article{border-top:1px solid #ddd;padding:24px 0;overflow-wrap:anywhere}img{max-width:260px;height:160px;object-fit:cover;float:right;margin:0 0 16px 20px}a{color:#17685b}</style><a href="/index">返回商城</a><h1>照片与开放数据来源</h1><p>虚构门店、原创演示套餐与演示分享不代表真实经营或消费。照片仅为题材配图，非虚构门店实景，不构成人物、品牌或场地背书。照片及其WebP/缩略图保留各自许可，与代码Apache许可分开。</p><p>开放场所数据：© OpenStreetMap contributors，<a href="https://www.openstreetmap.org/copyright">ODbL 1.0</a>；原始小样本与衍生场所表按ODbL提供，见仓库content/poi。开放场所未入驻本平台，不提供在售套餐或虚构评价。</p>'+''.join(rows)+'</html>'
    (ROOT/'hmdp-vue3/public/content-sources.html').write_text(page,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    catalog,assets=compile_catalog();attribution(assets)
    if not args.apply:
        print('Prepared catalog:',len(catalog['shops']),len(catalog['products']),len(catalog['stories']));return
    assert sql('SELECT DATABASE()').strip()=='hmdp_0'
    bootstrap=sql('SELECT (SELECT COUNT(*) FROM mall_product WHERE id BETWEEN 800001 AND 800030),(SELECT COUNT(*) FROM mall_sku WHERE id BETWEEN 900001 AND 900060)').strip()
    assert bootstrap=='30\t60','Missing original 30 products / 60 SKUs: run python scripts/seed_commerce.py before the first rich-content import'
    before=snapshot();counts_before=counts();backup=ROOT.parent/'archive'/BATCH;backup.mkdir(parents=True,exist_ok=True)
    for schema in ('hmdp_0','hmdp_1'):
        file=backup/(schema+'.sql')
        if not file.exists():
            with file.open('wb') as output:
                subprocess.run(['docker','compose','exec','-T','mysql','mysqldump','-uroot','-pplus-root-local','--single-transaction','--no-tablespaces',schema],cwd=ROOT,stdout=output,check=True)
    authors=[]
    for i,name in enumerate(('小禾','松子','阿木','圆圆','青柠','未央','方糖','河川','纸鸢','云朵','星野','小满')):
        a=login('181000000'+f'{i+1:02d}');uid=str(a['user']['id']);icon=f'/imgs/icons/demo-author-{i+1}.svg'
        path=ROOT/'hmdp-vue3/public'/icon.lstrip('/');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect rx="50" width="100" height="100" fill="hsl({i*29} 35% 82%)"/><text x="50" y="65" font-size="42" text-anchor="middle" font-family="sans-serif" fill="#17473f">{name[0]}</text></svg>',encoding='utf-8')
        nick=name+'·演示';data('/user/profile','PUT',{'nickName':nick,'icon':icon,'city':'上海·演示','introduce':'原创演示分享作者，不对应真实消费用户。'},a['token'])
        authors.append({'id':uid,'name':nick,'token':a['token']})
    # Establish genuine synthetic-account relationships through the existing API.
    for i,author in enumerate(authors):
        for delta in (1,3):data('/follow/'+authors[(i+delta)%12]['id']+'/true','PUT',token=author['token'])
    existing=sql('SELECT id FROM mall_product ORDER BY id').split()
    managed=sql("SELECT entity_id FROM mall_demo_record WHERE kind='product'").split()
    for p in catalog['products']:
        assert str(p['id']) not in existing or p['legacy'] or str(p['id']) in managed,'Unmanaged product ID collision'
    existing_shops=sql('SELECT id FROM tb_shop').split()
    managed_shops=sql("SELECT entity_id FROM mall_demo_record WHERE kind='shop'").split()
    for s in catalog['shops']:
        assert str(s['id']) not in existing_shops or 1001<=s['id']<=1012 or str(s['id']) in managed_shops,'Unmanaged shop ID collision'
    statements=['START TRANSACTION;'];skipped=[]
    frozen=set(sql("SELECT DISTINCT k.product_id FROM mall_seckill_activity a JOIN mall_sku k ON k.id=a.sku_id WHERE a.status IN ('ACTIVE','STOPPING','CONFIGURING')").split())
    for c,tid in TYPES.items():
        for schema in ('hmdp_0','hmdp_1'):
            statements.append(f"INSERT INTO {schema}.tb_shop_type(id,name,icon,sort) VALUES({tid},{q(c)},{q('/imgs/commerce/'+{'运动':'sport','手作':'craft','文娱':'play','休闲':'rest'}[c]+'.svg')},0) ON DUPLICATE KEY UPDATE name=VALUES(name),sort=0;")
    for s in catalog['shops']:
        for schema in ('hmdp_0','hmdp_1'):
            values=[s['id'],s['name'],s['typeId'],','.join(assets[k]['path'] for k in s['photos']),s['area'],s['address'],s['x'],s['y'],s['hours']]
            statements.append(f"INSERT INTO {schema}.tb_shop(id,name,type_id,images,area,address,x,y,open_hours,avg_price,sold,comments,score) VALUES({','.join(map(q,values))},0,0,0,0) ON DUPLICATE KEY UPDATE name=VALUES(name),type_id=VALUES(type_id),images=VALUES(images),area=VALUES(area),address=VALUES(address),x=VALUES(x),y=VALUES(y),open_hours=VALUES(open_hours);")
        values=[s['id'],'上海',s['area'],s['introduction'],s['audience'],s['arrivalTips'],s['hours'],'虚构门店；参考商圈坐标；开放照片非本店实景。',BATCH]
        statements.append(f"INSERT INTO mall_shop_profile VALUES({','.join(map(q,values))}) ON DUPLICATE KEY UPDATE district=VALUES(district),introduction=VALUES(introduction),audience=VALUES(audience),arrival_tips=VALUES(arrival_tips),hours=VALUES(hours),batch=VALUES(batch);")
        statements.append(record('shop',s['id'],s))
    for p in catalog['products']:
        active=str(p['id']) in frozen
        if active:skipped.append(p['id'])
        else:
            values=[p['id'],p['shopId'],p['title'],p['category'],p['cover'],p['description'],p['rules'],'ACTIVE']
            statements.append(f"INSERT INTO mall_product(id,shop_id,title,category,cover,description,rules,status) VALUES({','.join(map(q,values))}) ON DUPLICATE KEY UPDATE version=IF(title=VALUES(title) AND rules=VALUES(rules),version,version+1),title=VALUES(title),category=VALUES(category),cover=VALUES(cover),description=VALUES(description),rules=VALUES(rules);")
        if not p['legacy']:
            for v in range(2):
                sid=920000+(p['id']-820000)*2+v
                values=[sid,p['id'],'单人完整体验' if v==0 else '双人同行体验',f'{p["price"]*(1 if v==0 else 1.8):.2f}',12+(p['id']%8)*2]
                statements.append(f"INSERT IGNORE INTO mall_sku(id,product_id,name,price,available) VALUES({','.join(map(q,values))});")
        for i,key in enumerate(p['photos']):
            a=assets[key];values=[p['id'],i,key,a['path'],a['thumbnail'],a['caption']+' · 题材配图，非门店实景']
            statements.append(f"INSERT INTO mall_product_media VALUES({','.join(map(q,values))}) ON DUPLICATE KEY UPDATE asset_id=VALUES(asset_id),image_url=VALUES(image_url),thumbnail_url=VALUES(thumbnail_url),caption=VALUES(caption);")
        statements.append(record('product',p['id'],p))
    for story in catalog['stories']:
        values=[story['id'],story['shopId'],authors[story['authorIndex']]['id'],story['title'],','.join(story['images']),story['content'],story['createdAt'],story['createdAt']]
        for schema in ('hmdp_0','hmdp_1'):
            statements.append(f"INSERT INTO {schema}.tb_blog(id,shop_id,user_id,title,images,content,create_time,update_time,liked,comments) VALUES({','.join(map(q,values))},0,0) ON DUPLICATE KEY UPDATE title=VALUES(title),images=VALUES(images),content=VALUES(content);")
        statements.append(record('story',story['id'],story))
    poi=json.loads((ROOT/'content/poi/shanghai-sports-osm-sample.json').read_text(encoding='utf-8'));included=[]
    for row in poi['rows']:
        name=row.get('name') or row.get('nameEn')
        if not name:continue
        values=[row['sourceId'],name,row['category'],row['longitude'],row['latitude'],(row.get('street') or '')+(row.get('houseNumber') or ''),row['sourceUrl'],poi['osmBaseTimestamp'],'ODbL 1.0',BATCH]
        statements.append(f"INSERT INTO mall_reference_place VALUES({','.join(map(q,values))}) ON DUPLICATE KEY UPDATE name=VALUES(name),category=VALUES(category),longitude=VALUES(longitude),latitude=VALUES(latitude),address=VALUES(address),source_url=VALUES(source_url),source_timestamp=VALUES(source_timestamp);")
        included.append(row['sourceId'])
    statements.append('COMMIT;');sql('\n'.join(statements))
    after=snapshot();assert before==after,'Protected transactions or existing SKU state changed'
    # Rebuild only derived memberships for owned venues; application restart reloads Bloom data.
    commands=[]
    for s in catalog['shops']:
        for tid in TYPES.values():commands.append(('ZREM','shop:geo:'+str(tid),s['id']))
        commands.append(('GEOADD','shop:geo:'+str(s['typeId']),s['x'],s['y'],s['id']))
        commands.append(('DEL','cache:shop:'+str(s['id']),'hmdp-cache:shop:'+str(s['id']),'hmdp-cache:shop_null:'+str(s['id'])))
    follower_rows=sql('SELECT user_id,follow_user_id FROM tb_follow').splitlines()
    followers={}
    for line in follower_rows:
        follower,author=line.split('\t');followers.setdefault(author,[]).append(follower)
    for story in catalog['stories']:
        uid=authors[story['authorIndex']]['id'];score=int(datetime.datetime.fromisoformat(story['createdAt']).timestamp()*1000)
        for follower in followers.get(uid,[]):commands.append(('ZADD','feed:'+follower,score,story['id']))
    redis_batch(commands)
    report={'generated':datetime.datetime.now().isoformat(),'batch':BATCH,'shops':len(catalog['shops']),'products':len(catalog['products']),'stories':len(catalog['stories']),'photos':len(assets),'referencePlaces':len(included),'rawReferenceRows':len(poi['rows']),'countsBefore':counts_before,'countsAfter':counts(),'activeProductContentPreserved':skipped,'before':before,'after':after,'protectedStateUnchanged':before==after,'backup':str(backup),'authors':[{'id':a['id'],'name':a['name']} for a in authors]}
    (ROOT/'docs/evidence/content-import.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('before','after','authors')},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
