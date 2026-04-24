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

:: Backend API
echo [1/3] Iniciando FastAPI (porta 8888)...
start "IRAI-API" cmd /c "cd /d %ROOT% && python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8888"
timeout /t 3 /nobreak > nul

:: Worker Collector
echo [2/3] Iniciando Collector (intervalo 60s)...
start "IRAI-Collector" cmd /c "cd /d %ROOT% && python backend\workers\collector.py --interval 60 --force"

:: Frontend
echo [3/3] Iniciando Frontend (porta 5175)...
start "IRAI-Frontend" cmd /c "cd /d %ROOT%\frontend && npm run dev"

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
