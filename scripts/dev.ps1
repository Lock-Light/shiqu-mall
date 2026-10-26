param(
    [ValidateSet('start','build','status','stop','test','api','ui','labs','setup-ui')]
    [string]$Action='status'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}
function Ui-Python {
    $candidate=Join-Path $projectRoot '.runtime/ui-venv/Scripts/python.exe'
    if (!(Test-Path -LiteralPath $candidate)) { throw '先运行 ./scripts/dev.ps1 setup-ui' }
    return $candidate
}
function Build-All {
    Invoke-Checked { python scripts/prepare_local.py }
    Invoke-Checked { docker volume create hmdp-course_maven }
    Push-Location -LiteralPath (Join-Path $projectRoot 'hmdp-vue3')
    try {
        if (!(Test-Path -LiteralPath node_modules)) { Invoke-Checked { npm ci --ignore-scripts --no-audit --no-fund } }
        Invoke-Checked { npm run build }
    } finally { Pop-Location }
    Invoke-Checked { docker compose run --rm build }
    Invoke-Checked { docker compose build app commerce gateway }
}
function Run-Api { Invoke-Checked { & ./scripts/commerce.ps1 setup }; Invoke-Checked { & ./scripts/commerce.ps1 api } }
function Run-Ui { Invoke-Checked { & ./scripts/commerce.ps1 ui } }
switch ($Action) {
    'setup-ui' {
        Invoke-Checked { py -3 -m venv .runtime/ui-venv }
        $uiPython=Ui-Python
        Invoke-Checked { & $uiPython -m pip install -r scripts/requirements-ui.txt }
        Invoke-Checked { & $uiPython -m playwright install chromium }
    }
    'build' { Build-All }
    'start' {
        if (!(Test-Path -LiteralPath 'infra/seed/hmdp_0.sql') -or !(Test-Path -LiteralPath 'hmdp-vue3/dist/index.html') -or !(Test-Path -LiteralPath 'hmdp-core-service/target/hmdp-core-service-0.0.1-SNAPSHOT.jar') -or !(Test-Path -LiteralPath 'hmdp-commerce-service/target/hmdp-commerce-service-0.0.1-SNAPSHOT.jar') -or !(Test-Path -LiteralPath 'hmdp-gateway/target/hmdp-gateway-0.0.1-SNAPSHOT.jar')) { Build-All }
        Invoke-Checked { docker compose up -d --wait mysql redis rabbitmq nacos }
        Invoke-Checked { python scripts/migrate_commerce.py }
        Invoke-Checked { docker compose up -d --wait app commerce gateway web }
        Invoke-Checked { docker compose exec -T web openresty -s reload }
        Invoke-Checked { python scripts/wait_application_ready.py }
        Write-Host '拾趣体验商城: http://localhost:18091/index ; 首次使用另运行 python scripts/seed_commerce.py'
    }
    'status' { Invoke-Checked { docker compose ps } }
    'stop' { Invoke-Checked { docker compose stop } }
    'api' { Run-Api }
    'ui' { Run-Ui }
    'test' { Invoke-Checked { & ./scripts/commerce.ps1 all } }
    'labs' { Invoke-Checked { python scripts/advanced_labs.py } }
}
