[CmdletBinding()]
param(
    [switch]$SkipE2E,
    [switch]$SkipSecurity,
    [switch]$RunSonar,
    [switch]$InstallHook,
    [switch]$UninstallHook
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HookPath = Join-Path $RepoRoot ".git\hooks\pre-push"

if ($InstallHook) {
    $hookBody = @'
#!/bin/sh
echo "[Atenta pre-push] Ejecutando validacion local antes de hacer push..."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "codigo/scripts/pre-push-check.ps1"
exit $?
'@
    [System.IO.File]::WriteAllText($HookPath, $hookBody.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[OK] Hook pre-push instalado en: $HookPath" -ForegroundColor Green
    return
}

if ($UninstallHook) {
    if (Test-Path $HookPath) {
        Remove-Item $HookPath -Force
        Write-Host "[OK] Hook pre-push eliminado de: $HookPath" -ForegroundColor Green
    } else {
        Write-Host "[INFO] No habia un hook pre-push instalado." -ForegroundColor Yellow
    }
    return
}

$env:DISABLE_SQLALCHEMY_CEXT = "1"
$env:PYTHONIOENCODING = "utf-8"

$ReportsDir = Join-Path $RepoRoot "reports"
New-Item -ItemType Directory -Path $ReportsDir -Force | Out-Null

$BackendTargets = @(
    @{ Name = "auth-service"; MinCov = 78 },
    @{ Name = "llm-gateway";  MinCov = 78 },
    @{ Name = "back-chat";    MinCov = 72 }
)

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Atenta - Verificacion Local Pre-Push (Tests, Cobertura, Smoke)" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Backend unit tests + cobertura + normalizacion XML
foreach ($svc in $BackendTargets) {
    $svcName = $svc.Name
    $minCov = $svc.MinCov
    $svcDir = Join-Path $RepoRoot "codigo\$svcName"
    $covXml = Join-Path $ReportsDir "coverage-$svcName.xml"
    $junitXml = Join-Path $ReportsDir "junit-$svcName.xml"

    Write-Host "`n[1/4] Pytest + cobertura ($svcName >= $minCov%)..." -ForegroundColor Yellow
    Push-Location $svcDir
    try {
        python -m pytest -v `
            --cov=src `
            --cov-report=term-missing `
            --cov-report="xml:$covXml" `
            --junitxml="$junitXml" `
            --cov-fail-under="$minCov"
        if ($LASTEXITCODE -ne 0) {
            throw "Fallo pytest o el umbral de cobertura ($minCov%) en $svcName."
        }
    } finally {
        Pop-Location
    }

    python (Join-Path $RepoRoot "codigo\scripts\normalize_coverage.py") $covXml "codigo/$svcName"
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo normalize_coverage.py para $svcName."
    }
}

# 2. Frontend builds + npm audit produccion
foreach ($app in @("front-admin", "FRONT-MOCK")) {
    $appDir = Join-Path $RepoRoot "codigo\$app"
    Write-Host "`n[2/4] Build y npm audit produccion ($app)..." -ForegroundColor Yellow
    Push-Location $appDir
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Fallo 'npm run build' en $app."
        }
        npm audit --omit=dev --audit-level=high
        if ($LASTEXITCODE -ne 0) {
            throw "Se detectaron vulnerabilidades HIGH/CRITICAL en dependencias de produccion de $app."
        }
    } finally {
        Pop-Location
    }
}

# 3. Escaneo de seguridad Python (Bandit + pip-audit)
if (-not $SkipSecurity) {
    Write-Host "`n[3/4] Analisis SAST (Bandit) y CVEs Python (pip-audit)..." -ForegroundColor Yellow
    $banditCfg = Join-Path $RepoRoot ".bandit"
    $banditOut = Join-Path $ReportsDir "bandit-report.json"
    $srcDirs = @(
        (Join-Path $RepoRoot "codigo\auth-service\src"),
        (Join-Path $RepoRoot "codigo\llm-gateway\src"),
        (Join-Path $RepoRoot "codigo\back-chat\src")
    )

    python -m bandit -c $banditCfg -r @srcDirs -f json -o $banditOut --exit-zero | Out-Null
    python -m bandit -c $banditCfg -r @srcDirs -lll
    if ($LASTEXITCODE -ne 0) {
        throw "Bandit detecto hallazgos de severidad HIGH."
    }

    python -m pip_audit -s osv `
        -r (Join-Path $RepoRoot "codigo\auth-service\requirements.txt") `
        -r (Join-Path $RepoRoot "codigo\llm-gateway\requirements.txt") `
        -r (Join-Path $RepoRoot "codigo\back-chat\requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "pip-audit detecto vulnerabilidades en las dependencias backend."
    }
} else {
    Write-Host "`n[3/4] Omitiendo Bandit/pip-audit por -SkipSecurity." -ForegroundColor DarkGray
}

# 4. Smoke test E2E de los 5 servicios
if (-not $SkipE2E) {
    Write-Host "`n[4/4] Ejecutando Smoke Test E2E (5 servicios aislados)..." -ForegroundColor Yellow
    python (Join-Path $RepoRoot "codigo\scripts\e2e_smoke_test.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el smoke test E2E."
    }
} else {
    Write-Host "`n[4/4] Omitiendo Smoke Test E2E por -SkipE2E." -ForegroundColor DarkGray
}

# 5. SonarQube local opcional
if ($RunSonar) {
    Write-Host "`n[EXTRA] Ejecutando sonar-scanner local..." -ForegroundColor Yellow
    if (-not $env:SONAR_HOST_URL -or -not $env:SONAR_TOKEN) {
        throw "Para -RunSonar debes definir las variables de entorno SONAR_HOST_URL y SONAR_TOKEN."
    }
    Push-Location $RepoRoot
    try {
        sonar-scanner
        if ($LASTEXITCODE -ne 0) {
            throw "Fallo sonar-scanner."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "`n[EXITO] Todas las validaciones locales de Atenta pasaron." -ForegroundColor Green
