"""Create a recoverable source + transactional MySQL baseline before commerce changes."""
import datetime, hashlib, json, os, subprocess, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out = ROOT.parent / 'archive' / ('commerce-baseline-' + stamp)
out.mkdir(parents=True, exist_ok=False)
skip = {'node_modules', 'target', '.runtime', '.firecrawl', 'dist', '.idea'}
with zipfile.ZipFile(out / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for directory, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            file = Path(directory) / name
            z.write(file, file.relative_to(ROOT))
with (out / 'databases.sql').open('wb') as handle:
    subprocess.run(['docker', 'compose', 'exec', '-T', 'mysql', 'mysqldump',
                    '-uroot', '-pplus-root-local', '--single-transaction', '--routines',
                    '--databases', 'hmdp_0', 'hmdp_1'], cwd=ROOT, stdout=handle, check=True)
with zipfile.ZipFile(out / 'source.zip') as z:
    assert z.testzip() is None
manifest = {'created': stamp, 'root': str(ROOT), 'head': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'files': {}}
for file in out.iterdir():
    manifest['files'][file.name] = {'bytes': file.stat().st_size,
                                    'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
(out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
