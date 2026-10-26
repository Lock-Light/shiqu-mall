"""Small, attributed Commons photo selection; never downloads a bulk dataset."""
import argparse, concurrent.futures, datetime, hashlib, html, io, json, re, time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path
from PIL import Image, ImageDraw
from migrate_commerce import ROOT

TOPICS = [
 ('climb','indoor climbing wall','室内攀岩'),('yoga','yoga mat studio','瑜伽练习'),
 ('badminton','badminton court','羽毛球场'),('fitness','gym dumbbells','力量训练'),
 ('pottery','pottery wheel clay','陶艺拉坯'),('wood','woodworking hand tools','木作工具'),
 ('dye','indigo dyeing fabric','靛蓝染织'),('photo','camera photography','摄影器材'),
 ('board','board game table','桌游场景'),('guitar','acoustic guitar','原声吉他'),
 ('paper','origami paper folding','折纸作品'),('tea','tea ceremony teapot','茶席器具'),
 ('pingpong','table tennis table','乒乓球台'),('archery','archery target bow','射箭练习'),
 ('fencing','fencing training','击剑练习'),('boxing','boxing gloves','拳击器材'),
 ('flower','flower arrangement','花艺作品'),('leather','leatherworking tools','皮具手作'),
 ('silver','silversmith tools','银工工具'),('print','linocut printing','版画制作'),
 ('drums','drum kit','架子鼓'),('paint','watercolor painting palette','水彩绘画'),
 ('calligraphy','Chinese calligraphy brush ink','书法笔墨'),('theatre','theatre stage rehearsal','舞台排练'),
 ('chess','chess board pieces','国际象棋'),('coffee','pour over coffee','手冲咖啡'),
 ('bake','bread dough kneading','面包制作'),('garden','succulent plants pots','多肉园艺'),
 ('walk','Shanghai architecture street','城市漫步'),('reading','library reading room interior','阅读空间'),
 ('scent','perfume bottles','香气器具'),('camp','camping tent outdoors','露营装备'),
 ('climb2','bouldering indoor','抱石岩点'),('pottery2','handmade ceramic cups','陶器作品'),
 ('wood2','wood carving workshop','木雕工作'),('flower2','floristry bouquet','花束'),
 ('coffee2','coffee beans brewing','咖啡豆'),('tea2','Chinese tea leaves','茶叶'),
 ('board2','wooden board games','桌游棋子'),('garden2','terrarium plants glass','微景观植物')]

def clean(value):
    return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',str(value)))).strip()

def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent':'ShiquEducationalDemo/1.0 (Commons attribution preserved; local demo)'}),timeout=35) as response:
                return response.read()
        except HTTPError as error:
            if attempt==2:raise
            delay=max(10,int(error.headers.get('Retry-After','30'))) if error.code==429 else 2+attempt
            print('HTTP',error.code,'waiting',delay,'seconds before retry',flush=True)
            time.sleep(delay)
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)

def candidates(topic):
    key,query,caption=topic
    cache=ROOT/'.runtime/content-sources'/f'{key}.json'
    if cache.exists():
        prior=json.loads(cache.read_text(encoding='utf-8'))
        if prior['query']==query:return prior
    url='https://commons.wikimedia.org/w/api.php?'+urlencode({'action':'query','format':'json','generator':'search','gsrsearch':'filetype:bitmap '+query,'gsrnamespace':6,'gsrlimit':6,'prop':'imageinfo','iiprop':'url|extmetadata|mime|size','iiurlwidth':1200})
    time.sleep(1.5)
    data=json.loads(fetch(url));items=[]
    for page in sorted(data.get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',99)):
        info=page.get('imageinfo',[{}])[0];m=info.get('extmetadata',{})
        license=clean(m.get('LicenseShortName',{}).get('value',''))
        if not (license.startswith('CC BY ') or license.startswith('CC BY-SA ') or license=='CC0'):continue
        if info.get('mime') not in ('image/jpeg','image/png') or min(info.get('width',0),info.get('height',0))<450:continue
        items.append({'title':page['title'],'sourcePage':info['descriptionurl'],'downloadUrl':info.get('thumburl',info['url']),'originalUrl':info['url'],'author':clean(m.get('Artist',{}).get('value','')),'license':license,'licenseUrl':clean(m.get('LicenseUrl',{}).get('value','')),'description':clean(m.get('ImageDescription',{}).get('value','')),'rawMetadata':m})
    result={'id':key,'query':query,'caption':caption,'candidates':items,'queriedAt':datetime.datetime.now().isoformat()}
    cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def prepare(topic,choices):
    data=candidates(topic);key=data['id'];selected=choices.get(key,0)
    item=data['candidates'][selected]
    assert not re.search(r'AI.generated|generative artificial|stable diffusion|midjourney',str(item['rawMetadata']),re.I),key+' is not an accepted photograph'
    target=ROOT/'hmdp-vue3/public/imgs/content';target.mkdir(parents=True,exist_ok=True)
    raw_path=ROOT/'.runtime/content-originals'/f'{key}-{selected}.img';raw_path.parent.mkdir(parents=True,exist_ok=True)
    if not raw_path.exists():raw_path.write_bytes(fetch(item['downloadUrl']))
    raw=raw_path.read_bytes();im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1440,1200))
    path=target/f'{key}.webp';im.save(path,'WEBP',quality=84,method=6)
    thumb=im.copy();thumb.thumbnail((520,420));thumb_path=target/f'{key}-thumb.webp';thumb.save(thumb_path,'WEBP',quality=80,method=6)
    result={k:v for k,v in item.items() if k!='rawMetadata'}
    result.update({'assetId':key,'caption':data['caption'],'path':f'/imgs/content/{key}.webp','thumbnail':f'/imgs/content/{key}-thumb.webp','downloadedAt':datetime.datetime.now().isoformat(),'downloadedSourceSha256':hashlib.sha256(raw).hexdigest(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb_path.read_bytes()).hexdigest(),'dimensions':list(im.size),'modifications':'Converted the Commons source rendition to WebP, downscaled without cropping; thumbnail downscaled separately. Derivatives retain source license.','usage':'题材演示配图，非虚构门店实景，不代表人物/场地背书。','metadataFile':'content/photo-source-metadata.json#'+key})
    return result

def restore_pinned():
    manifest=json.loads((ROOT/'content/photo-manifest.json').read_text(encoding='utf-8'))
    target=ROOT/'hmdp-vue3/public'
    for item in manifest:
        full=target/item['path'].lstrip('/');thumb=target/item['thumbnail'].lstrip('/')
        if full.exists() and thumb.exists() and hashlib.sha256(full.read_bytes()).hexdigest()==item['sha256'] and hashlib.sha256(thumb.read_bytes()).hexdigest()==item['thumbnailSha256']:continue
        raw=fetch(item['downloadUrl'])
        assert hashlib.sha256(raw).hexdigest()==item['downloadedSourceSha256'],'Pinned source changed: '+item['assetId']
        im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1440,1200));full.parent.mkdir(parents=True,exist_ok=True);im.save(full,'WEBP',quality=84,method=6)
        im.thumbnail((520,420));im.save(thumb,'WEBP',quality=80,method=6)
        assert hashlib.sha256(full.read_bytes()).hexdigest()==item['sha256'],'Use the recorded Pillow version for reproducible encoding'
        assert hashlib.sha256(thumb.read_bytes()).hexdigest()==item['thumbnailSha256']
    print('Verified/restored 40 pinned photographs; no search ranking used')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--metadata-only',action='store_true');parser.add_argument('--refresh-search',action='store_true');args=parser.parse_args()
    if (ROOT/'content/photo-manifest.json').exists() and not args.metadata_only and not args.refresh_search:
        restore_pinned();return
    choices_path=ROOT/'content/asset-choices.json';choices=json.loads(choices_path.read_text(encoding='utf-8')) if choices_path.exists() else {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        results=list(pool.map(candidates if args.metadata_only else lambda t:prepare(t,choices),TOPICS))
    folder=ROOT/'content';folder.mkdir(exist_ok=True)
    (folder/('photo-candidates.json' if args.metadata_only else 'photo-manifest.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.metadata_only:
        metadata={topic[0]:candidates(topic)['candidates'][choices.get(topic[0],0)] for topic in TOPICS}
        (folder/'photo-source-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        sheet=Image.new('RGB',(1000,((len(results)+4)//5)*154),'white');draw=ImageDraw.Draw(sheet)
        for i,asset in enumerate(results):
            img=Image.open(ROOT/'hmdp-vue3/public'/asset['thumbnail'].lstrip('/'));img.thumbnail((194,126));x=(i%5)*200;y=(i//5)*154;sheet.paste(img,(x,y));draw.text((x+3,y+130),asset['assetId'],fill='black')
        sheet.save(ROOT/'docs/evidence/content-contact-sheet.jpg')
    print('Prepared',len(results),'metadata entries' if args.metadata_only else 'licensed local photographs')

if __name__=='__main__':main()
