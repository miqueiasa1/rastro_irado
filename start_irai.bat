@echo off
title IRAI — Intraday Risk Appetite Index
echo ==================================================
echo   IRAI — Iniciando sistema
echo   %DATE% %TIME%
echo ==================================================
echo.

set ROOT=%~dp0
set PYTHONPATH=%ROOT%
set PYTHONIOENCODING=utf-8

echo [0/4] Encerrando processos antigos (Limpando portas 8888 e 5175)...
:: Tenta fechar as janelas do sistema anterior (se houver)
taskkill /F /FI "WINDOWTITLE eq IRAI-*" /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Administrador: IRAI-*" /T > nul 2>&1

:: Garante que as portas 8888 (API) e 5175 (Frontend) estão livres
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888" ^| find "LISTENING"') do taskkill /f /pid %%a > nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5175" ^| find "LISTENING"') do taskkill /f /pid %%a > nul 2>&1
timeout /t 2 /nobreak > nul

:: Backend API
echo [1/4] Iniciando FastAPI (porta 8888)...
start "IRAI-API" cmd /c "cd /d %ROOT% && :loop && python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8888 || (echo [API CAIU] Reiniciando em 5s... && timeout /t 5 && goto loop)"
timeout /t 3 /nobreak > nul

:: Worker Collector
echo [2/4] Iniciando Collector (intervalo 20s)...
start "IRAI-Collector" cmd /c "cd /d %ROOT% && :loop && python backend\workers\collector.py --interval 20 --force || (echo [COLLECTOR CAIU] Reiniciando em 5s... && timeout /t 5 && goto loop)"

:: Frontend
echo [3/4] Iniciando Frontend (porta 5175)...
start "IRAI-Frontend" cmd /c "cd /d %ROOT%\frontend && npm run dev"

:: Firebase Sync
echo [4/4] Iniciando Firebase Sync...
start "IRAI-FirebaseSync" cmd /c "cd /d %ROOT% && :loop && python scripts\firebase_sync.py || (echo [FIREBASE SYNC CAIU] Reiniciando em 5s... && timeout /t 5 && goto loop)"

timeout /t 3 /nobreak > nul
echo.
echo ==================================================
echo   IRAI rodando!
echo   API:       http://localhost:8888
echo   Dashboard: http://localhost:5175
echo   Swagger:   http://localhost:8888/docs
echo ==================================================
echo.
echo Pressione qualquer tecla para abrir o dashboard...
pause > nul
start http://localhost:5175
