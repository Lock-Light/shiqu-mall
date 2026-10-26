"""Additive, checksummed commerce migrations. No resetting existing business data."""
import argparse, hashlib, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def sql(statement, schema='hmdp_0'):
    return subprocess.check_output(['docker','compose','exec','-T','mysql','mysql',
        '-uroot','-pplus-root-local','--default-character-set=utf8mb4','-N','-B',schema],
        input=statement.encode('utf-8'),cwd=ROOT).decode('utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--schema',default='hmdp_0');a=p.parse_args()
    if a.schema not in ('hmdp_0','hmdp_commerce_test'):raise ValueError('Explicit commerce schema required')
    sql('CREATE TABLE IF NOT EXISTS mall_schema_migration(version VARCHAR(80) PRIMARY KEY, checksum CHAR(64) NOT NULL, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)',a.schema)
    for path in sorted((ROOT/'infra/migrations').glob('V*__*.sql')):
        body=path.read_text(encoding='utf-8');digest=hashlib.sha256(body.encode()).hexdigest()
        found=sql("SELECT checksum FROM mall_schema_migration WHERE version='"+path.name+"'",a.schema).strip()
        if found:
            if found!=digest:raise RuntimeError('Migration checksum mismatch: '+path.name)
            print('already applied',path.name);continue
        sql(body,a.schema)
        sql("INSERT INTO mall_schema_migration(version,checksum) VALUES ('"+path.name+"','"+digest+"')",a.schema)
        print('applied',path.name)
if __name__=='__main__':main()
