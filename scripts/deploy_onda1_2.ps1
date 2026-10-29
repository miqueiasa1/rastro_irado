# =====================================================================
#  Deploy das Ondas 1 e 2 da auditoria IRAI (fuso/sessão B3 + Regra 4)
#  EXECUTAR COMO ADMINISTRADOR, APÓS O FECHAMENTO DA B3 (>= 18:35 BRT)
#
#  Passos:
#   1. Backup consistente do banco (API de backup do SQLite, seguro com WAL)
#   2. Para os serviços IRAI (API, Collector, FirebaseSync)
#   3. Copia os arquivos alterados do worktree (rastro_irado_onda1) para produção
#   4. Migra o histórico B3 de BRT para o relógio do broker
#   5. Roda os testes
#   6. Sobe os serviços novamente
#  Rollback: pare os serviços, restaure o backup do banco e faça
#            `git checkout -- <arquivos>` / copie os .bak gerados no passo 3.
# =====================================================================
$ErrorActionPreference = "Stop"
$Prod = "C:\Users\ryzen\Downloads\Antigravity\rastro_irado"
$Dev  = "C:\Users\ryzen\Downloads\Antigravity\rastro_irado_onda1"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = "D:\irai_backups"
if (-not (Test-Path "D:\")) { $BackupDir = "$Prod\data\backups" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Files = @(
  "backend\timeconv.py",
  "backend\irai\engine.py",
  "backend\irai\nwe.py",
  "backend\api\main.py",
  "backend\workers\collector.py",
  "scripts\health_watchdog.py",
  "scripts\calibrate_universal.py",
  "scripts\migrate_b3_broker_time.py",
  "frontend\src\utils\time.js",
  "frontend\src\hooks\useIraiData.js",
  "frontend\src\components\TVGarchVolChart.jsx",
  "frontend\src\App.jsx",
  "tests\test_timeconv.py",
  "tests\test_nwe_gap.py",
  "tests\test_engine_session_invariants.py"
)

$brt = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), "E. South America Standard Time")
if ($brt.Hour -lt 18 -or ($brt.Hour -eq 18 -and $brt.Minute -lt 35)) {
  if ($brt.DayOfWeek -ne "Saturday" -and $brt.DayOfWeek -ne "Sunday") {
    throw "B3 ainda aberta ($($brt.ToString('HH:mm')) BRT). Rode após 18:35."
  }
}

Write-Host "[1/6] Backup do banco -> $BackupDir" -ForegroundColor Cyan
python -c "import sqlite3;s=sqlite3.connect(r'$Prod\data\irai_live.db');d=sqlite3.connect(r'$BackupDir\irai_live_pre_onda12_$Stamp.db');s.backup(d);d.close();print('backup ok')"

Write-Host "[2/6] Parando serviços" -ForegroundColor Cyan
Stop-Service IRAI_Collector, IRAI_FirebaseSync, IRAI_API -ErrorAction Continue

Write-Host "[3/6] Copiando arquivos (originais salvos como .bak_$Stamp)" -ForegroundColor Cyan
foreach ($f in $Files) {
  $src = Join-Path $Dev $f; $dst = Join-Path $Prod $f
  if (Test-Path $dst) { Copy-Item $dst "$dst.bak_$Stamp" }
  New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
  Copy-Item $src $dst -Force
  Write-Host "   $f"
}

Write-Host "[4/6] Migrando histórico B3 (BRT -> relógio do broker)" -ForegroundColor Cyan
Push-Location $Prod
python scripts\migrate_b3_broker_time.py --db data\irai_live.db --apply

Write-Host "[5/6] Testes" -ForegroundColor Cyan
python -m pytest tests -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Testes falharam — serviços NÃO foram religados. Avalie rollback." }
Pop-Location

Write-Host "[6/6] Subindo serviços" -ForegroundColor Cyan
Start-Service IRAI_API, IRAI_Collector, IRAI_FirebaseSync
Get-Service IRAI_* | Format-Table Name, Status

Write-Host "[extra] Build + deploy do frontend (Firebase Hosting)" -ForegroundColor Cyan
Push-Location "$Prod\frontend"
npm run build
npx firebase deploy --only hosting
Pop-Location

Write-Host "`nDeploy concluído. Próximo passo: recalibrar  ->  python scripts\calibrate_universal.py --all --force" -ForegroundColor Green
