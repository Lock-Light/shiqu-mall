"""Host HTTPS download avoids container Central connectivity failures; versions are pinned."""
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
from migrate_commerce import ROOT
runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
launcher=runtime/'junit-console.jar'
if not launcher.exists():
    url='https://maven.aliyun.com/repository/public/org/junit/platform/junit-platform-console-standalone/1.12.2/junit-platform-console-standalone-1.12.2.jar'
    with urlopen(url,timeout=30) as response:launcher.write_bytes(response.read())
with ZipFile(launcher) as z:assert z.testzip() is None
libs=runtime/'junit-libs';libs.mkdir(exist_ok=True)
for stale in libs.glob('*.jar'):stale.unlink()
with ZipFile(ROOT/'hmdp-commerce-service/target/hmdp-commerce-service-0.0.1-SNAPSHOT.jar') as z:
    for name in z.namelist():
        if name.startswith('BOOT-INF/lib/') and name.endswith('.jar'):(libs/Path(name).name).write_bytes(z.read(name))
print('JUnit Console 1.12.2 prepared; tests run real MySQL and never count build as a pass.')
