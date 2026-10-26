"""Read-only complete-table fingerprints for protecting the two live business schemas."""
import argparse,datetime,hashlib,json
from migrate_commerce import ROOT,sql
p=argparse.ArgumentParser();p.add_argument('label',choices=['before','after']);a=p.parse_args()
tables=sql("SELECT TABLE_SCHEMA,TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA IN ('hmdp_0','hmdp_1') AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA,TABLE_NAME").splitlines()
statements=[]
for row in tables:
    schema,table=row.split('\t')
    # Known server-owned identifiers, never request parameters. Sort every column
    # so tables with composite keys or no primary key also hash deterministically.
    columns=sql(f"SELECT COLUMN_NAME FROM information_schema.columns WHERE TABLE_SCHEMA='{schema}' AND TABLE_NAME='{table}' ORDER BY ORDINAL_POSITION").splitlines()
    name=f'{schema}.{table}'
    order=','.join('`'+c+'`' for c in columns)
    statements.append(f"SELECT '__MIGRATION_TABLE__={name}'; SELECT * FROM `{schema}`.`{table}` ORDER BY {order}")
raw=sql(';'.join(statements));fingerprints={}
for block in raw.split('__MIGRATION_TABLE__=')[1:]:
    name,_,body=block.partition('\n')
    fingerprints[name]={'sha256':hashlib.sha256(body.encode()).hexdigest(),'rows':len(body.splitlines())}
report={'generated':datetime.datetime.now().isoformat(),'label':a.label,'tables':fingerprints}
path=ROOT/f'docs/evidence/migration-data-{a.label}.json'
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if a.label=='after':
    before=json.loads((ROOT/'docs/evidence/migration-data-before.json').read_text(encoding='utf-8'))['tables']
    differences=[k for k in before.keys()|fingerprints.keys() if before.get(k)!=fingerprints.get(k)]
    assert not differences,('Business data changed during migration',differences)
print(f'{len(fingerprints)} live tables fingerprinted: {a.label}')
