"""Capture the deployed microservice artifacts; never treats historical results as new passes."""
import datetime, hashlib, json, subprocess
from urllib.parse import urlencode
from zipfile import ZipFile
from migrate_commerce import ROOT

def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,encoding='utf-8').strip()

services=[json.loads(line) for line in command('docker','compose','ps','--format','json').splitlines() if line]
expected={'app','commerce','gateway','mysql','redis','rabbitmq','nacos','web'}
assert {r['Service'] for r in services}==expected
assert all(r['State']=='running' and r['Health'] in ('','healthy') for r in services)
assert not command('docker','ps','--filter','label=com.docker.compose.project=hmdp-commerce-test','--format','{{.Names}}')
artifacts={}
for service,module in [('app','hmdp-core-service'),('commerce','hmdp-commerce-service'),('gateway','hmdp-gateway')]:
    path=ROOT/f'{module}/target/{module}-0.0.1-SNAPSHOT.jar'
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    deployed=command('docker','compose','exec','-T',service,'sha256sum','/app/app.jar').split()[0]
    assert digest==deployed,(service,'stale deployed jar')
    with ZipFile(path) as z:libs=sorted(n.split('/')[-1] for n in z.namelist() if n.startswith('BOOT-INF/lib/') and n.endswith('.jar'))
    assert not any('kafka' in name.lower() for name in libs)
    assert 'nacos-client-3.0.3.jar' in libs
    if service=='gateway':assert not any(n.startswith('spring-webmvc-') for n in libs)
    artifacts[service]={'sha256':digest,'deployedJarMatches':True,'libraries':libs}
stats=[json.loads(line) for line in command('docker','stats','--no-stream','--format','{{json .}}',*[r['Name'] for r in services]).splitlines()]
registrations={}
for name in ('hmdp-core','hmdp-commerce','hmdp-gateway'):
    url='http://localhost:8848/nacos/v1/ns/instance/list?'+urlencode({'serviceName':name,'groupName':'shiqu'})
    hosts=json.loads(command('docker','compose','exec','-T','nacos','curl','-fsS',url))['hosts']
    assert len(hosts)==1 and hosts[0]['healthy'] and hosts[0]['enabled'],(name,hosts)
    registrations[name]=[{k:h[k] for k in ('ip','port','healthy')} for h in hosts]
report={'generated':datetime.datetime.now().isoformat(),'services':[{k:r.get(k) for k in ('Name','Service','Image','State','Health')} for r in services], 'artifacts':artifacts,'stats':stats,'nacosServices':registrations,'testContainersRemaining':0,'note':'One local memory snapshot; not peak capacity. Historical test reports retain their original scope.'}
(ROOT/'docs/evidence/migration-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'services':len(services),'deployedJarMatches':True,'memory':{r['Name']:r['MemUsage'] for r in stats}},ensure_ascii=False,indent=2))
