"""Disposable, real Redis experiments. Only containers created by this run are removed."""
import argparse, binascii, concurrent.futures, json, os, socket, subprocess, time, uuid, traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evidence'; OUT.mkdir(parents=True,exist_ok=True)
RUN='hmdp-plus-lab-'+uuid.uuid4().hex[:8]
NODES={}; RESULTS=[]; REPORT=OUT/'advanced-labs.json'

def command(*args,check=True,timeout=120,input=None):
    p=subprocess.run(list(map(str,args)),input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    if check and p.returncode: raise RuntimeError(f'{args[:5]}: {p.stderr[-1800:]} {p.stdout[-1800:]}')
    return p.stdout.strip()

def wait(fn,timeout=35):
    end=time.monotonic()+timeout; last=None
    while time.monotonic()<end:
        try:
            result=fn()
            if result:return result
        except Exception as e:last=e
        time.sleep(.3)
    raise AssertionError(f'Condition did not converge in {timeout}s; last error={last}')

def node(name,*options,image='redis:7.4-alpine',sentinel=None):
    full=RUN+'-'+name
    base=['docker','run','-d','--name',full,'--label','purpose=hmdp-plus-lab','--network',RUN,'--memory','96m','--cpus','0.5','-p','127.0.0.1::6379']
    if sentinel:
        script="printf '%s\\n' "+' '.join("'"+line+"'" for line in sentinel)+" > /tmp/sentinel.conf; exec redis-server /tmp/sentinel.conf --sentinel"
        cid=command(*base,image,'sh','-c',script)
    else:cid=command(*base,image,'redis-server','--save','',*options)
    NODES[name]=cid
    wait(lambda:cli(name,'PING')=='PONG')
    return cid

def cli(name,*args,redirect=False):
    return command('docker','exec',NODES[name],'redis-cli',*(['-c'] if redirect else []),'--raw',*args)

def ip(name):return command('docker','inspect','--format',f'{{{{(index .NetworkSettings.Networks "{RUN}").IPAddress}}}}',NODES[name])
def info(name,section):
    return dict(line.split(':',1) for line in cli(name,'INFO',section).splitlines() if ':' in line and not line.startswith('#'))
def stop(name):command('docker','kill','--signal','KILL',NODES[name])
def start(name):command('docker','start',NODES[name]);wait(lambda:cli(name,'PING')=='PONG')
def check(name,fn):
    began=time.time()
    try:data=fn();result={'name':name,'status':'passed','seconds':round(time.time()-began,3),'observed':data}
    except Exception as e:result={'name':name,'status':'failed','seconds':round(time.time()-began,3),'error':repr(e),'traceback':traceback.format_exc()}
    RESULTS.append(result);REPORT.write_text(json.dumps({'run':RUN,'results':RESULTS},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)

class RedisError(Exception):pass
class RESP:
    """Course raw-socket client: encode RESP arrays and parse RESP2 values recursively."""
    def __init__(self,name):
        address=command('docker','port',NODES[name],'6379/tcp').split(':');self.sock=socket.create_connection((address[0],int(address[1])),5);self.file=self.sock.makefile('rb')
    @staticmethod
    def encode(args):
        values=[str(a).encode() for a in args]
        return b'*'+str(len(values)).encode()+b'\r\n'+b''.join(b'$'+str(len(v)).encode()+b'\r\n'+v+b'\r\n' for v in values)
    def read(self):
        line=self.file.readline();tag=line[:1];body=line[1:-2]
        if tag==b'+':return body.decode()
        if tag==b'-':raise RedisError(body.decode())
        if tag==b':':return int(body)
        if tag==b'$':
            length=int(body)
            if length<0:return None
            value=self.file.read(length);assert self.file.read(2)==b'\r\n';return value.decode()
        if tag==b'*':return [self.read() for _ in range(int(body))]
        raise ValueError(line)
    def call(self,*args):self.sock.sendall(self.encode(args));return self.read()
    def pipeline(self,commands):self.sock.sendall(b''.join(self.encode(c) for c in commands));return [self.read() for _ in commands]
    def close(self):self.file.close();self.sock.close()

def persistence():
    node('rdb');cli('rdb','SET','snapshot','saved');cli('rdb','SAVE');cli('rdb','SET','after-snapshot','not-saved');stop('rdb');start('rdb')
    assert cli('rdb','GET','snapshot')=='saved' and cli('rdb','EXISTS','after-snapshot')=='0'
    node('aof','--appendonly','yes','--appendfsync','always');cli('aof','SET','journal','durable');stop('aof');start('aof');assert cli('aof','GET','journal')=='durable'
    cli('rdb','BGSAVE');wait(lambda:info('rdb','persistence')['rdb_bgsave_in_progress']=='0')
    return {'rdb_saved_key_survives':True,'rdb_unsaved_write_lost':True,'aof_write_survives_SIGKILL':True,'fork_observation':info('rdb','persistence')}

def replication_and_sentinel():
    node('primary','--repl-diskless-sync-delay','0','--repl-backlog-size','1mb')
    for name in ['replica1','replica2']:node(name,'--replicaof',ip('primary'),'6379')
    wait(lambda:info('primary','replication').get('connected_slaves')=='2' and all(info(n,'replication').get('master_link_status')=='up' for n in ['replica1','replica2']))
    cli('primary','SET','replication-check','full');cli('primary','WAIT','2','5000');assert cli('replica1','GET','replication-check')=='full'
    before=info('primary','stats')
    replica_ip=ip('replica1')
    clients=[dict(field.split('=',1) for field in row.split() if '=' in field) for row in cli('primary','CLIENT','LIST','TYPE','REPLICA').splitlines()]
    replica_client=next(client['id'] for client in clients if client['addr'].split(':')[0]==replica_ip)
    command('docker','network','disconnect',RUN,NODES['replica1']);time.sleep(1)
    # A short network disconnect can leave TCP alive. Force this replica connection closed so PSYNC is actually exercised.
    cli('primary','CLIENT','KILL','ID',replica_client)
    cli('primary','SET','replication-check','partial')
    command('docker','network','connect',RUN,NODES['replica1'])
    wait(lambda:cli('replica1','GET','replication-check')=='partial',45)
    wait(lambda:int(info('primary','stats')['sync_partial_ok'])>int(before['sync_partial_ok']))
    after=info('primary','stats')
    master_ip=ip('primary')
    for name in ['sentinel1','sentinel2','sentinel3']:
        node(name,sentinel=['port 6379','bind 0.0.0.0','protected-mode no',f'sentinel monitor course-master {master_ip} 6379 2','sentinel down-after-milliseconds course-master 1500','sentinel failover-timeout course-master 10000','sentinel parallel-syncs course-master 1'])
    wait(lambda:'num-other-sentinels\n2' in cli('sentinel1','SENTINEL','MASTER','course-master').replace('\r',''))
    initial=cli('sentinel1','SENTINEL','get-master-addr-by-name','course-master').splitlines()
    stop('primary')
    def elected():
        state=cli('sentinel1','SENTINEL','get-master-addr-by-name','course-master').splitlines()
        return state if state and state[0]!=initial[0] else None
    promoted=wait(elected,45)
    promoted_name=next(n for n in ['replica1','replica2'] if ip(n)==promoted[0]);assert cli(promoted_name,'SET','after-failover','yes')=='OK'
    start('primary');wait(lambda:info('primary','replication').get('role')=='slave',45)
    java_topology(sentinel=True)
    return {'full_syncs':after.get('sync_full'),'partial_resync_before':before['sync_partial_ok'],'partial_resync_after':after['sync_partial_ok'],'sentinel_old_master':initial,'sentinel_new_master':promoted,'old_master_rejoined_as_replica':True,'RedisTemplate_sentinel':'passed'}

def java_topology(sentinel=False,cluster=False):
    args=['docker','run','--rm','--network',RUN,'-v',str(ROOT)+':/workspace','-v','hmdp-course_maven:/root/.m2','-w','/workspace/labs/redis','-e','MAVEN_OPTS=-Xmx384m -XX:ActiveProcessorCount=2']
    if sentinel:args+=['-e','COURSE_SENTINELS='+','.join(ip(n)+':6379' for n in ['sentinel1','sentinel2','sentinel3'])]
    if cluster:args+=['-e','COURSE_CLUSTER='+','.join(ip('cluster'+str(n))+':6379' for n in range(1,7))]
    args+=['maven:3.9.11-eclipse-temurin-17','mvn','-B','-ntp','-Dtest=CourseTopologyTest#'+('redisTemplateThroughSentinel' if sentinel else 'redisTemplateThroughCluster'),'test']
    output=command(*args,timeout=240);(OUT/('redis-template-sentinel.log' if sentinel else 'redis-template-cluster.log')).write_text(output,encoding='utf-8');assert 'BUILD SUCCESS' in output

def cluster():
    for i in range(1,9):node('cluster'+str(i),'--cluster-enabled','yes','--cluster-node-timeout','1200','--cluster-require-full-coverage','yes')
    addresses=[ip('cluster'+str(i))+':6379' for i in range(1,7)]
    create=cli('cluster1','--cluster','create',*addresses,'--cluster-replicas','1','--cluster-yes');assert '16384 slots covered' in create
    wait(lambda:'cluster_state:ok' in cli('cluster1','CLUSTER','INFO'))
    cli('cluster1','SET','{course}:one','a',redirect=True);assert cli('cluster2','GET','{course}:one',redirect=True)=='a'
    cross=cli('cluster1','MSET','alpha','1','beta','2',redirect=True);assert 'CROSSSLOT' in cross
    assert cli('cluster1','MSET','{same}:a','1','{same}:b','2',redirect=True)=='OK'
    assert any('MOVED' in cli('cluster1','GET',f'redirect:{i}') for i in range(20))
    old_id=cli('cluster1','CLUSTER','MYID');new_id=cli('cluster7','CLUSTER','MYID')
    cli('cluster1','--cluster','add-node',ip('cluster7')+':6379',addresses[0])
    cli('cluster1','--cluster','add-node',ip('cluster8')+':6379',addresses[0],'--cluster-slave','--cluster-master-id',new_id)
    wait(lambda:'master_link_status:up' in cli('cluster8','INFO','replication'))
    tag=next(str(i) for i in range(100000) if binascii.crc_hqx(str(i).encode(),0)%16384==0);key='{'+tag+'}:migrating'
    cli('cluster1','SET',key,'kept-through-migration',redirect=True)
    moved=cli('cluster1','--cluster','reshard',addresses[0],'--cluster-from',old_id,'--cluster-to',new_id,'--cluster-slots','256','--cluster-yes')
    assert cli('cluster7','GET',key)=='kept-through-migration'
    cli('cluster7','WAIT','1','5000');stop('cluster7')
    wait(lambda:info('cluster8','replication').get('role')=='master',45)
    wait(lambda:'cluster_state:ok' in cli('cluster1','CLUSTER','INFO'),45)
    assert cli('cluster1','GET',key,redirect=True)=='kept-through-migration'
    start('cluster7');wait(lambda:info('cluster7','replication').get('role')=='slave',45)
    java_topology(cluster=True)
    return {'initial_slots':16384,'cross_slot_rejected':cross,'same_hash_tag_MSET':'OK','MOVED_observed':True,'expanded_to_masters':4,'slots_migrated':256,'migrated_key_preserved':True,'replica8_promoted_after_SIGKILL':True,'old_master_rejoined':True,'RedisTemplate_cluster':'passed'}

def encoding_and_optimization():
    node('encoding',image='redis:6.2-alpine')
    c=RESP('encoding');observed={}
    try:
        assert c.call('EVAL','local function twice(v) return v*2 end local sum=0 for i=1,5 do if i%2==1 then sum=sum+twice(i) end end return sum',0)==18
        c.call('RPUSH','fifo','one','two');assert c.call('LPOP','fifo')=='one' and c.call('LPOP','fifo')=='two'
        assert c.call('PUBLISH','course-events','offline-message')==0
        subscriber=RESP('encoding')
        try:
            assert subscriber.call('SUBSCRIBE','course-events')==['subscribe','course-events',1]
            assert c.call('PUBLISH','course-events','live-message')==1
            assert subscriber.read()==['message','course-events','live-message']
        finally:subscriber.close()
        c.call('SET','int','42');c.call('SET','short','hello');c.call('SET','long','x'*100)
        for k in ['int','short','long']:observed[k]=c.call('OBJECT','ENCODING',k)
        c.call('SADD','set',1,2,3);observed['set_numeric']=c.call('OBJECT','ENCODING','set');c.call('SADD','set','word');observed['set_mixed']=c.call('OBJECT','ENCODING','set')
        c.call('HSET','hash','f','v');observed['hash_small']=c.call('OBJECT','ENCODING','hash');c.call('HSET','hash','big','x'*100);observed['hash_large_value']=c.call('OBJECT','ENCODING','hash')
        c.call('ZADD','zset',1,'a');observed['zset_small']=c.call('OBJECT','ENCODING','zset');c.call('ZADD','zset',2,'x'*100);observed['zset_large']=c.call('OBJECT','ENCODING','zset')
        c.call('RPUSH','list','a','b');observed['list']=c.call('OBJECT','ENCODING','list')
        assert observed['hash_small']=='ziplist' and observed['set_numeric']=='intset' and observed['zset_large']=='skiplist'
        node('encoding7');modern=RESP('encoding7')
        try:
            modern.call('HSET','small-hash','field','value');modern.call('ZADD','small-zset',1,'a')
            modern_encodings={'version':info('encoding7','server')['redis_version'],'hash':modern.call('OBJECT','ENCODING','small-hash'),'zset':modern.call('OBJECT','ENCODING','small-zset')}
            assert modern_encodings['hash']=='listpack' and modern_encodings['zset']=='listpack'
        finally:modern.close()
        seq=[['SET',f'batch:{i}',i] for i in range(500)]
        began=time.perf_counter()
        for request in seq:c.call(*request)
        sequential=time.perf_counter()-began;began=time.perf_counter();assert c.pipeline(seq)==['OK']*500;pipeline=time.perf_counter()-began
        assert c.call('MSET','m:1',1,'m:2',2)=='OK' and c.call('MGET','m:1','m:2')==['1','2']
        c.call('CONFIG','SET','slowlog-log-slower-than',0);c.call('GET','short');slow=c.call('SLOWLOG','GET',2);assert slow
        c.call('CONFIG','SET','slowlog-log-slower-than',10000)
        c.call('SET','bigkey','x'*200000);bigmemory=c.call('MEMORY','USAGE','bigkey');assert bigmemory>200000;c.call('UNLINK','bigkey')
        for i in range(100):c.call('SET',f'jitter:{i}','v','EX',30+i%11)
        ttl=[c.call('TTL',f'jitter:{i}') for i in range(100)];assert max(ttl)-min(ttl)>=9
        c.call('SET','expires','x','PX',150);time.sleep(.2);assert c.call('GET','expires') is None
        c.call('CONFIG','SET','maxmemory','4mb');c.call('CONFIG','SET','maxmemory-policy','allkeys-lru')
        c.pipeline([['SET',f'eviction:{i}','x'*20000] for i in range(350)])
        assert int(info('encoding','stats')['evicted_keys'])>0
        c.call('CONFIG','SET','maxmemory-policy','noeviction')
        rejected=False
        try:
            for i in range(500):c.call('SET',f'noeviction:{i}','x'*20000)
        except RedisError as e:rejected='OOM' in str(e)
        assert rejected
        c.call('CONFIG','SET','maxmemory','0');c.call('ACL','SETUSER','readonly','on','>lab-only','~public:*','+get')
        readonly=RESP('encoding')
        try:
            readonly.call('AUTH','readonly','lab-only')
            try:readonly.call('SET','public:x','x');raise AssertionError('ACL allowed write')
            except RedisError as e:assert 'NOPERM' in str(e)
        finally:readonly.close()
        return {'Redis_version':info('encoding','server')['redis_version'],'encodings':observed,'modern_encoding_comparison':modern_encodings,'Lua_variables_loop_function_condition_result':18,'Redis_List_FIFO':True,'PubSub_online_only':True,'raw_RESP_socket_client':True,'sequential_500_ms':round(sequential*1000,3),'pipeline_500_ms':round(pipeline*1000,3),'bigkey_memory_bytes':bigmemory,'slowlog_observed':True,'TTL_jitter_range':[min(ttl),max(ttl)],'expired_key_unreadable':True,'evicted_keys':info('encoding','stats')['evicted_keys'],'noeviction_OOM':True,'ACL_write_denied':True,'io_backend':info('encoding','server').get('multiplexing_api')}
    finally:c.close()

def jvm_scope():
    args=['docker','run','--rm','--network','none','--memory','192m','-v',str(ROOT)+':/src:ro','maven:3.9.11-eclipse-temurin-17','java','-Xmx64m','/src/scripts/JvmLockProbe.java']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        observed=list(pool.map(lambda _:json.loads(command(*args)),range(2)))
    overlap=min(o['end'] for o in observed)-max(o['begin'] for o in observed);assert overlap>0
    return {'two_JVM_intervals':observed,'overlap_ms':overlap,'synchronized_does_not_exclude_other_JVM':True}

def epoll():
    output=command('docker','run','--rm','--network','none','--memory','192m','-v',str(ROOT)+':/src:ro','gcc:15-bookworm','sh','-c','gcc -O2 -Wall -Wextra /src/scripts/epoll_lab.c -o /tmp/epoll-lab && /tmp/epoll-lab')
    return json.loads(output)

def hll_million():
    node('uv-million');client=RESP('uv-million')
    try:
        for offset in range(0,1000000,1000):client.call('PFADD','course:uv:million',*['visitor:'+str(i) for i in range(offset,offset+1000)])
        estimated=client.call('PFCOUNT','course:uv:million');error=abs(estimated-1000000)/1000000
        assert error<.03
        client.call('PFADD','course:uv:million','visitor:0','visitor:1');assert client.call('PFCOUNT','course:uv:million')==estimated
        return {'distinct_input':1000000,'estimated':estimated,'relative_error':error,'memory_bytes':client.call('MEMORY','USAGE','course:uv:million'),'duplicates_do_not_increase_estimate':True}
    finally:client.close()

def redis_client_mechanisms():
    node('mechanisms')
    output=command('docker','run','--rm','--network',RUN,'-v',str(ROOT)+':/workspace','-v','hmdp-course_maven:/root/.m2','-w','/workspace/labs/redis','-e','MAVEN_OPTS=-Xmx384m -XX:ActiveProcessorCount=2','-e','LAB_REDIS='+ip('mechanisms'),'maven:3.9.11-eclipse-temurin-17','mvn','-B','-ntp','-Dtest=RedisMechanismsTest','test',timeout=240)
    (OUT/'redis-client-mechanisms.log').write_text(output,encoding='utf-8')
    assert 'BUILD SUCCESS' in output and 'Failures: 0, Errors: 0, Skipped: 0' in output
    c=RESP('mechanisms')
    try:
        entry=c.call('XADD','lab:stream','*','voucher','demo')
        assert c.call('XGROUP','CREATE','lab:stream','workers','0')=='OK'
        received=c.call('XREADGROUP','GROUP','workers','consumer-a','COUNT',1,'STREAMS','lab:stream','>')
        assert received[0][1][0][0]==entry
        assert c.call('XPENDING','lab:stream','workers')[0]==1
        replay=c.call('XREADGROUP','GROUP','workers','consumer-a','COUNT',1,'STREAMS','lab:stream','0')
        assert replay[0][1][0][0]==entry
        assert c.call('XACK','lab:stream','workers',entry)==1
        assert c.call('XPENDING','lab:stream','workers')[0]==0
    finally:c.close()
    return {'RedisTemplate_Hash_long_id':True,'Lua_safe_unlock_after_lease':True,'Redisson_reentrant':True,'watchdog_renews_after_3s':True,'MultiLock_two_clients':True,'Stream_pending_replay_ACK':True,'Java_tests':2,'skipped':0}

def main():
    global REPORT
    parser=argparse.ArgumentParser();parser.add_argument('--only');parser.add_argument('--report',default='advanced-labs.json');args=parser.parse_args();REPORT=OUT/args.report
    command('docker','network','create','--label','purpose=hmdp-plus-lab',RUN)
    try:
        for name,fn in [('RDB-AOF-fork',persistence),('replication-sentinel',replication_and_sentinel),('cluster-slots-reshard-failover',cluster),('encoding-RESP-best-practices',encoding_and_optimization),('synchronized-JVM-scope',jvm_scope),('Linux-epoll-ET-LT',epoll),('HLL-million-visitors',hll_million),('Redis-client-locks-Stream',redis_client_mechanisms)]:
            if not args.only or name in args.only.split(','):check(name,fn)
    finally:
        for name,cid in reversed(list(NODES.items())):
            label=command('docker','inspect','--format','{{index .Config.Labels "purpose"}}',cid,check=False)
            if label=='hmdp-plus-lab':command('docker','rm','-f',cid,check=False)
        command('docker','network','rm',RUN,check=False)
    report={'run':RUN,'finished_at':time.strftime('%Y-%m-%d %H:%M:%S'),'passed':sum(r['status']=='passed' for r in RESULTS),'failed':sum(r['status']=='failed' for r in RESULTS),'results':RESULTS,'cleanup':'only this run\'s labeled container IDs and network'}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(1 if report['failed'] else 0)
if __name__=='__main__':main()
