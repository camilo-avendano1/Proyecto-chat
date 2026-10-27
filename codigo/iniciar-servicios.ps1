# ==============================================================================
# Script de Inicio de Microservicios SaaS Core Chat & Diagnóstico
# Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno
# ==============================================================================

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Iniciando Ecosistema de Microservicios SaaS Core" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan

$env:DISABLE_SQLALCHEMY_CEXT = "1"
$baseDir = $PSScriptRoot

Write-Host "[1/4] Iniciando Auth Service (Sesiones de Widgets y Administradores) en puerto 8002..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "[Console]::Title='Auth Service :8002'; cd '$baseDir\auth-service'; `$env:DISABLE_SQLALCHEMY_CEXT='1'; python -m uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload"

Start-Sleep -Seconds 2

Write-Host "[2/4] Iniciando LLM Gateway (Aislamiento de Modelos y Contabilidad de Tokens) en puerto 8003..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "[Console]::Title='LLM Gateway :8003'; cd '$baseDir\llm-gateway'; `$env:DISABLE_SQLALCHEMY_CEXT='1'; python -m uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload"

Start-Sleep -Seconds 2

Write-Host "[3/4] Iniciando Back Central Chat (Diagnóstico y Guardrails RAG) en puerto 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "[Console]::Title='Back Central Chat :8000'; cd '$baseDir\back-chat'; `$env:DISABLE_SQLALCHEMY_CEXT='1'; python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 2

Write-Host "[4/4] Iniciando FRONT-MOCK (Simulador y Panel de Observabilidad) en puerto 5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "[Console]::Title='FRONT-MOCK :5173'; cd '$baseDir\FRONT-MOCK'; npm run dev"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Servicios desplegados con exito:" -ForegroundColor Green
Write-Host "  * Auth Service:   http://localhost:8002/docs" -ForegroundColor White
Write-Host "  * LLM Gateway:    http://localhost:8003/docs" -ForegroundColor White
Write-Host "  * Back Chat:      http://localhost:8000/docs" -ForegroundColor White
Write-Host "  * Front Mock:     http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Credenciales de Administradores Sembradas:" -ForegroundColor Magenta
Write-Host "  * SUPERADMIN:   superadmin    / AdminSuperSecret2025!  (Global)" -ForegroundColor White
Write-Host "  * CLIENT_ADMIN: sigires_admin / AdminSigires2025!      (Empresa: SIGIRES)" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
