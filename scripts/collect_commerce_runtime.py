"""Record only this project's runtime, image and deployed JAR identity."""
import datetime
import hashlib
import json
import subprocess
from migrate_commerce import ROOT


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


services = [json.loads(line) for line in command('docker', 'compose', 'ps', '--format', 'json').splitlines() if line]
assert len(services) == 5 and {row['Service'] for row in services} == {'app', 'web', 'mysql', 'redis', 'kafka'}
assert all(row['State'] == 'running' for row in services)
assert not command('docker', 'ps', '--filter', 'label=com.docker.compose.project=hmdp-commerce-test', '--format', '{{.Names}}')
names = [row['Name'] for row in services]
stats = [json.loads(line) for line in command('docker', 'stats', '--no-stream', '--format', '{{json .}}', *names).splitlines()]
jar = ROOT / 'hmdp-core-service/target/hmdp-core-service-0.0.1-SNAPSHOT.jar'
host_hash = hashlib.sha256(jar.read_bytes()).hexdigest()
deployed_hash = command('docker', 'compose', 'exec', '-T', 'app', 'sha256sum', '/app/app.jar').split()[0]
assert host_hash == deployed_hash, 'Deployed JAR differs from verified artifact'
app_name = next(row['Name'] for row in services if row['Service'] == 'app')
report = {
    'generated': datetime.datetime.now().isoformat(),
    'project': 'hmdp-plus',
    'note': 'One local memory snapshot, not a capacity or peak-memory measurement. No unrelated resources removed.',
    'services': [{key: row.get(key) for key in ('Name', 'Service', 'Image', 'State', 'Health')} for row in services],
    'stats': stats,
    'testContainersRemaining': 0,
    'appImageId': command('docker', 'inspect', '--format', '{{.Image}}', app_name),
    'jarSha256': host_hash,
    'deployedJarMatches': True,
}
(ROOT / 'docs/evidence/commerce-runtime.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'services': len(services), 'deployedJarMatches': True, 'testContainersRemaining': 0, 'memory': {row['Name']: row['MemUsage'] for row in stats}}, ensure_ascii=False, indent=2))
