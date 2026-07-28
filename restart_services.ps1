Write-Host "Parando todos os processos MetaTrader 5..." -ForegroundColor Yellow
Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Parando todos os processos Python..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "Aguardando NSSM reiniciar os servicos..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

Write-Host "Status dos servicos:" -ForegroundColor Green
Get-Service -Name IRAI_API, IRAI_Collector, IRAI_FirebaseSync, IRAI_Frontend | Format-Table Name, Status

Write-Host "Pronto! Servicos reiniciados." -ForegroundColor Green
Read-Host "Pressione Enter para fechar"
