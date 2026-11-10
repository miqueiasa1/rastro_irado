@echo off
REM Relatorio diario de assertividade (fase 15, v2.0). Chamado pela tarefa "IRAI Daily Assertividade" (seg-sex 18:45).
REM So le o irai_live.db (mode=ro); grava em data\eval\, data\reports\ e logs\eval_assertividade.log.
setlocal
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist logs mkdir logs
echo ==== %date% %time% inicio >> logs\eval_assertividade.log
C:\Python313\python.exe scripts\eval_assertividade.py --window-sessions 20 --persist >> logs\eval_assertividade.log 2>&1
set RC1=%ERRORLEVEL%
C:\Python313\python.exe scripts\eval_assertividade.py --start 2026-08-03 --persist >> logs\eval_assertividade.log 2>&1
set RC2=%ERRORLEVEL%
echo ==== %date% %time% fim rc_janela20=%RC1% rc_periodo=%RC2% >> logs\eval_assertividade.log
if not "%RC1%"=="0" exit /b %RC1%
exit /b %RC2%