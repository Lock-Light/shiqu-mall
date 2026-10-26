"""Build a fresh, isolated /dingping/ demo release without changing local credentials.

Exports a short quiesced MySQL/Redis/upload snapshot, resumes the local services,
then removes local sessions from a separate Redis snapshot container. No test
fixtures or existing production volumes are restored by this script.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(list(args), cwd=ROOT, check=True, **kwargs)


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        raise SystemExit('Use a NEW release directory; refusing to overwrite it.')
    out.mkdir(parents=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    creds = {k: secrets.token_hex(24) for k in ('MYSQL_ROOT', 'MYSQL_APP', 'REDIS', 'RABBIT')}
    write(out / '.env', ''.join(f'SHIQU_{k}_PASSWORD={v}\n' for k,v in creds.items()))
    write(out / 'config/application-local.yaml',
          (ROOT/'infra/application-local.yaml').read_text(encoding='utf-8').replace('plus-local', creds['REDIS']))
    write(out / 'config/shardingsphere.yaml',
          (ROOT/'infra/shardingsphere.yaml').read_text(encoding='utf-8').replace('plus-local', creds['MYSQL_APP']))
    (out/'data/init').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'infra/public-mysql-users.sh',out/'data/init/00-users.sh')
    nginx = (ROOT/'infra/nginx.conf').read_text(encoding='utf-8')
    nginx = nginx.replace('  server {', '''  limit_req_zone $binary_remote_addr zone=otp:1m rate=10r/m;
  map $arg_phone $public_demo_phone {
    default 0;
    "18000000004" 1;
    "18000000005" 1;
  }
  server {''',1)
    nginx = nginx.replace('    location /api/ {', '''    # Spring MVC strips matrix parameters; reject ambiguous paths before proxying.
    if ($uri ~ ";") { return 400; }
    rewrite ^/dingping/(.*)$ /$1 last;
    location = /dingping { return 308 /dingping/; }
    location ^~ /api/user/code {
      default_type application/json;
      if ($public_demo_phone = 0) {
        return 403 '{"success":false,"errorMsg":"公开演示仅支持体验账号18000000004和18000000005；门店账号请联系维护者。"}';
      }
      limit_req zone=otp burst=8 nodelay;
      limit_req_status 429;
      proxy_pass http://gateway:8080/user/code$is_args$args;
      proxy_set_header Authorization $http_authorization;
    }
    location /assets/ { try_files $uri =404; }
    location /brand/ { try_files $uri =404; }
    location /api/ {''',1)
    # Namespace servlet cookies when multiple demos share one public IP.
    nginx = nginx.replace('    client_max_body_size 10m;',
                          '    client_max_body_size 10m;\n    proxy_cookie_path / /dingping/;')
    # Public API exposes no Spring management endpoints through this web proxy.
    nginx = nginx.replace('    location /assets/', '    location ^~ /api/actuator { return 404; }\n    location /assets/',1)
    write(out/'config/nginx.conf', nginx)
    cfg = json.loads(subprocess.check_output(['docker','compose','config','--format','json'],cwd=ROOT))
    cfg['name'] = 'dingping'
    cfg.pop('networks', None)
    cfg['networks'] = {'default': {}, 'edge': {'external':True, 'name':'dingping-edge'}}
    cfg['volumes'] = {k:{} for k in ('mysql','redis','rabbitmq','nacos','uploads')}
    cfg['services'].pop('build',None)
    sv = cfg['services']
    release_images = []
    for name,target in [('app','core'),('commerce','commerce'),('gateway','gateway')]:
        image = f'shiqu/{target}:{stamp}'
        run('docker','tag',sv[name]['image'],image)
        sv[name]['image']=image
        sv[name].pop('build',None)
        sv[name].pop('ports',None)
        release_images.append(image)
    # Resolve local bind mounts into portable release-relative paths.
    sv['mysql']['volumes']=['mysql:/var/lib/mysql','./data/init:/docker-entrypoint-initdb.d:ro']
    sv['mysql']['environment']['MYSQL_ROOT_PASSWORD']='${SHIQU_MYSQL_ROOT_PASSWORD:?required}'
    sv['mysql']['environment']['MYSQL_APP_PASSWORD']='${SHIQU_MYSQL_APP_PASSWORD:?required}'
    sv['mysql']['healthcheck']['test']=['CMD-SHELL','MYSQL_PWD="$$MYSQL_APP_PASSWORD" mysql --protocol=TCP -h127.0.0.1 -uhmdp hmdp_1 -e "SELECT COUNT(*) FROM tb_shop" >/dev/null 2>&1']
    sv['redis']['volumes']=['redis:/data']
    sv['redis']['command']=['redis-server','--requirepass','${SHIQU_REDIS_PASSWORD:?required}','--appendonly','yes']
    sv['redis']['environment']={'REDISCLI_AUTH':'${SHIQU_REDIS_PASSWORD:?required}'}
    sv['redis']['healthcheck']['test']=['CMD','redis-cli','ping']
    sv['rabbitmq']['volumes']=['rabbitmq:/var/lib/rabbitmq']
    sv['rabbitmq']['environment']['RABBITMQ_DEFAULT_PASS']='${SHIQU_RABBIT_PASSWORD:?required}'
    sv['nacos']['volumes']=['nacos:/home/nacos/data']
    sv['app']['volumes']=['./config/application-local.yaml:/config/application-local.yaml:ro','./config/shardingsphere.yaml:/config/shardingsphere.yaml:ro','uploads:/uploads']
    for name in ('app','commerce'):
        sv[name].setdefault('environment',{}).update({
            'SPRING_DATA_REDIS_PASSWORD':'${SHIQU_REDIS_PASSWORD:?required}',
            'SPRING_RABBITMQ_PASSWORD':'${SHIQU_RABBIT_PASSWORD:?required}',
        })
    sv['commerce']['environment']['COMMERCE_PASSWORD']='${SHIQU_MYSQL_APP_PASSWORD:?required}'
    sv['web']['volumes']=['./config/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro','./web:/web:ro','uploads:/uploads:ro']
    sv['web']['ports']=['127.0.0.1:${SHIQU_WEB_PORT:-18091}:80']
    sv['web']['networks']={'default':{},'edge':{'aliases':['dingping-web']}}
    sv['web']['healthcheck']={'test':['CMD-SHELL','wget -q -O /dev/null http://127.0.0.1/index.html'],'interval':'10s','retries':15}
    for service in sv.values():
        service['restart']='unless-stopped'
        service['logging']={'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}
    sv['restore']={'image':'redis:7.4-alpine','profiles':['restore'],'entrypoint':['sh','/snapshot/restore.sh'],
        'volumes':['redis:/restore/redis','uploads:/restore/uploads','./data:/snapshot:ro']}
    write(out/'compose.yaml',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
    shutil.copy2(ROOT/'infra/public-restore.sh',out/'data/restore.sh')
    shutil.copy2(ROOT/'scripts/wait_application_ready.py',out/'wait_application_ready.py')
    # Keep the root-mounted local build intact.
    subprocess.run(['npm.cmd' if os.name=='nt' else 'npm','run','build','--','--base=/dingping/','--outDir='+str(out/'web')],cwd=ROOT/'hmdp-vue3',check=True)
    def assert_queues_empty():
        rows=subprocess.check_output(['docker','compose','exec','-T','rabbitmq','rabbitmqctl','-q','list_queues','name','messages_ready','messages_unacknowledged'],cwd=ROOT).decode()
        for row in rows.splitlines():
            fields=row.split('\t')
            if len(fields)==3 and fields[1].isdigit() and fields[2].isdigit():
                if int(fields[1])+int(fields[2]):
                    raise RuntimeError('Drain RabbitMQ before snapshot: '+fields[0])
    assert_queues_empty()
    print('Frontend built; taking a short application-quiesced demo snapshot.',flush=True)
    try:
        run('docker','compose','stop','web','gateway','commerce','app')
        assert_queues_empty()
        with gzip.open(out/'data/init/10-data.sql.gz','wb',compresslevel=6) as f:
            dump=subprocess.Popen(['docker','compose','exec','-T','mysql','mysqldump','-uroot','-pplus-root-local','--single-transaction','--routines','--events','--triggers','--hex-blob','--set-gtid-purged=OFF','--no-tablespaces','--databases','hmdp_0','hmdp_1'],cwd=ROOT,stdout=subprocess.PIPE)
            shutil.copyfileobj(dump.stdout,f)
            if dump.wait()!=0: raise RuntimeError('MySQL snapshot failed')
        run('docker','compose','exec','-T','redis','redis-cli','-a','plus-local','SAVE')
        run('docker','cp','hmdp-plus-redis-1:/data/dump.rdb',str(out/'data/redis.rdb'))
        run('docker','cp','hmdp-plus-web-1:/uploads',str(out/'data/uploads'))
    finally:
        run('docker','compose','up','-d','--wait','app','commerce','gateway','web')
        run('python','scripts/wait_application_ready.py')
    # Sanitize only the COPY. Never delete local live sessions.
    clean_name='dingping-snapshot-'+stamp
    try:
        run('docker','run','-d','--name',clean_name,'--network','none','-v',str(out/'data')+':/snapshot','redis:7.4-alpine','redis-server','--appendonly','no','--dir','/snapshot','--dbfilename','redis.rdb')
        import time
        for _ in range(30):
            ping=subprocess.run(['docker','exec',clean_name,'redis-cli','ping'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if ping.returncode==0:break
            time.sleep(.2)
        lua="local n=0; for _,pattern in ipairs({'login:*','lock:*','redisson_lock*','test:*','commerce-test*'}) do local c='0'; repeat local r=redis.call('SCAN',c,'MATCH',pattern,'COUNT',1000); c=r[1]; for _,k in ipairs(r[2]) do n=n+redis.call('DEL',k) end until c=='0' end; return n"
        run('docker','exec',clean_name,'redis-cli','EVAL',lua,'0')
        remaining=subprocess.check_output(['docker','exec',clean_name,'redis-cli','--scan','--pattern','login:*']).strip()
        if remaining:raise RuntimeError('Snapshot still contains local login data')
        run('docker','exec',clean_name,'redis-cli','SAVE')
    finally:
        subprocess.run(['docker','rm','-f',clean_name],stdout=subprocess.DEVNULL)
    images=release_images+[sv[n]['image'] for n in ('mysql','redis','rabbitmq','nacos','web')]
    write(out/'release.json',json.dumps({'release':stamp,'basePath':'/dingping/','images':images,'demoPhones':['18000000004','18000000005'],'source':'java-up-up/hmdp-plus plus local changes','payment':'simulation only','snapshot':'quiesced dual-schema MySQL + Redis, login sessions/codes excluded'},ensure_ascii=False,indent=2)+'\n')
    print('Exporting 8 linux/amd64 images; shared layers are stored once.',flush=True)
    with gzip.open(out/'images.tar.gz','wb',compresslevel=1) as f:
        proc=subprocess.Popen(['docker','image','save',*images],stdout=subprocess.PIPE)
        shutil.copyfileobj(proc.stdout,f)
        if proc.wait()!=0:raise RuntimeError('Image export failed')
    sums=[]
    for path in sorted(out.rglob('*')):
        if path.is_file():
            digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
            sums.append(digest+'  '+path.relative_to(out).as_posix())
    write(out/'SHA256SUMS','\n'.join(sums)+'\n')
    archive=out.with_suffix('.tar')
    with tarfile.open(archive,'w') as tf:
        # Explicit directory modes survive a restrictive extraction umask, so
        # MySQL's uid 999 can traverse its mounted initialization directory.
        for path in sorted(p for p in out.rglob('*') if p.is_dir()):
            info=tf.gettarinfo(str(path),arcname=path.relative_to(out).as_posix())
            info.mode=0o755
            tf.addfile(info)
        for path in sorted(out.rglob('*')):
            if path.is_file():
                info=tf.gettarinfo(str(path),arcname=path.relative_to(out).as_posix())
                info.mode=0o600 if path.name in ('.env','redis.rdb') or path.suffix=='.gz' or path.name in ('application-local.yaml','shardingsphere.yaml') else 0o644
                if path.name=='00-users.sh':
                    info.mode=0o755  # Official MySQL executes instead of sourcing it.
                if path.relative_to(out).as_posix()=='data/init/10-data.sql.gz':
                    info.uid=info.gid=999  # mysql:8.4's actual container uid/gid.
                    info.uname=info.gname='mysql'
                with path.open('rb') as f:tf.addfile(info,f)
    digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    write(archive.with_suffix('.tar.sha256'),digest+'  '+archive.name+'\n')
    print(json.dumps({'releaseDirectory':str(out),'archive':str(archive),'sha256':digest,'archiveBytes':archive.stat().st_size},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
