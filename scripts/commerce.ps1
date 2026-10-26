param([ValidateSet('setup','unit','api','ui','seckill','legacy','architecture','report','all','stop')][string]$Action='setup')
$ErrorActionPreference='Stop'
$commerceRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $commerceRoot
function Checked([scriptblock]$command){& $command;if($LASTEXITCODE -ne 0){throw "Command failed: $LASTEXITCODE"}}
function Test-Setup {
    Checked {python scripts/prepare_commerce_test.py}
    Checked {python scripts/migrate_commerce.py --schema hmdp_commerce_test}
    Checked {docker compose -f compose.commerce-test.yaml up -d --wait}
    Checked {docker compose -f compose.commerce-test.yaml exec -T commerce-test-web openresty -s reload}
    $previousPlusUrl=$env:PLUS_URL
    try{$env:PLUS_URL='http://127.0.0.1:18092';Checked {python scripts/seed_commerce.py --test}}
    finally{if($null -eq $previousPlusUrl){Remove-Item Env:PLUS_URL -ErrorAction SilentlyContinue}else{$env:PLUS_URL=$previousPlusUrl}}
    Checked {python scripts/wait_application_ready.py --base http://127.0.0.1:18092}
}
function Unit {
    Checked {docker compose -f compose.commerce-test.yaml down}
    Checked {python scripts/prepare_commerce_test.py}
    Checked {python scripts/migrate_commerce.py --schema hmdp_commerce_test}
    Checked {docker compose run --rm build mvn -q -DskipTests package}
    Checked {python scripts/prepare_junit.py}
    Checked {docker compose run --rm build java '-Duser.timezone=Asia/Shanghai' -cp '/workspace/hmdp-commerce-service/target/classes:/workspace/hmdp-commerce-service/target/test-classes:/workspace/.runtime/junit-console.jar:/workspace/.runtime/junit-libs/*' org.junit.platform.console.ConsoleLauncher execute --select-class org.javaup.commerce.CommerceServiceIntegrationTest --select-class org.javaup.commerce.RabbitDeliveryIntegrationTest --reports-dir /workspace/.runtime/migration-commerce-junit --details summary}
}
function Ui {Checked {& ./.runtime/ui-venv/Scripts/python.exe scripts/verify_commerce_ui.py};Checked {& ./.runtime/ui-venv/Scripts/python.exe scripts/verify_commerce_seckill_ui.py}}
function Legacy {
    $previousPlusUrl=$env:PLUS_URL
    try{$env:PLUS_URL='http://127.0.0.1:18092';Checked {python scripts/verify_api.py};Checked {& ./.runtime/ui-venv/Scripts/python.exe scripts/verify_ui.py}}
    finally{if($null -eq $previousPlusUrl){Remove-Item Env:PLUS_URL -ErrorAction SilentlyContinue}else{$env:PLUS_URL=$previousPlusUrl}}
}
switch($Action){
 'setup'{Test-Setup}
 'unit'{Unit}
 'api'{Checked {python scripts/verify_commerce_api.py}}
 'ui'{Ui}
 'seckill'{Checked {python scripts/verify_commerce_seckill.py}}
 'legacy'{Legacy}
 'architecture'{Checked {python scripts/verify_microservices.py}}
 'report'{Checked {python scripts/collect_migration_report.py}}
 'stop'{Checked {docker compose -f compose.commerce-test.yaml down}}
 'all'{Unit;Checked {docker compose build app commerce gateway};Test-Setup;Checked {python scripts/verify_commerce_api.py};Checked {python scripts/verify_commerce_seckill.py};Ui;Legacy;Checked {python scripts/verify_microservices.py};Checked {python scripts/collect_migration_report.py};Checked {docker compose -f compose.commerce-test.yaml down}}
}
