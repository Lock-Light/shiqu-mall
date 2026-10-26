"""Aggregate only newly executed migration evidence; fail on missing/failed checks."""
import datetime,json,xml.etree.ElementTree as ET
from migrate_commerce import ROOT
out=ROOT/'docs/evidence';groups=[]
for file in ('migration-commerce-api.json','migration-commerce-seckill.json','migration-commerce-ui.json','migration-commerce-seckill-ui.json','migration-legacy-api-commerce.json','migration-legacy-ui-commerce.json','migration-architecture.json'):
    data=json.loads((out/file).read_text(encoding='utf-8'));checks=data['checks']
    assert checks and all(c['passed'] for c in checks),file
    assert not (data.get('pageerrors') or data.get('pageErrors')),file
    groups.append({'source':file,'checks':len(checks),'passed':len(checks)})
junit=ET.parse(ROOT/'.runtime/migration-commerce-junit/TEST-junit-jupiter.xml').getroot()
assert int(junit.attrib['failures'])==int(junit.attrib['errors'])==int(junit.attrib['skipped'])==0
count=int(junit.attrib['tests']);assert count==13
groups.insert(0,{'source':'migration-junit-jupiter.xml','checks':count,'passed':count})
(out/'migration-junit-jupiter.xml').write_bytes((ROOT/'.runtime/migration-commerce-junit/TEST-junit-jupiter.xml').read_bytes())
report={'generated':datetime.datetime.now().isoformat(),'groups':groups,'total':sum(g['checks'] for g in groups),'scope':'13 JUnit integration tests plus HTTP/browser/fault groups; not all unit tests or a production capacity claim'}
(out/'migration-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
