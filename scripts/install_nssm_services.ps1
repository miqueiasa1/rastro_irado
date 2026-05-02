$ErrorActionPreference = "Stop"

$RootDir = (Get-Item -Path ".\").FullName
$PythonPath = (Get-Command python).Source

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: nssm não encontrado no PATH do Windows." -ForegroundColor Red
    Write-Host "Baixe em nssm.cc e adicione à variável de ambiente PATH, ou instale via choco: choco install nssm"
    exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Instalando Serviços do IRAI (via NSSM)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

function Install-Service {
    param(
        [string]$ServiceName,
        [string]$AppDirectory,
        [string]$AppParameters
    )

    Write-Host "Instalando: $ServiceName..."
    
    # Remove se já existir
    try {
        $check = nssm status $ServiceName 2>&1
        if ($check -notmatch "Can't open service") {
            nssm stop $ServiceName | Out-Null
            nssm remove $ServiceName confirm | Out-Null
            Start-Sleep -Seconds 2
        }
    } catch {
        # Ignora erro se o serviço não existir
    }

    nssm install $ServiceName $PythonPath $AppParameters | Out-Null
    nssm set $ServiceName AppDirectory $AppDirectory | Out-Null
    nssm set $ServiceName AppStdout "$AppDirectory\logs\$ServiceName.log" | Out-Null
    nssm set $ServiceName AppStderr "$AppDirectory\logs\$ServiceName.error.log" | Out-Null
    nssm set $ServiceName AppRotateFiles 1 | Out-Null
    nssm set $ServiceName AppRotateOnline 0 | Out-Null
    nssm set $ServiceName AppRotateBytes 5242880 | Out-Null # 5MB limit
    nssm set $ServiceName AppEnvironmentExtra "PYTHONPATH=C:\Users\ryzen\AppData\Roaming\Python\Python313\site-packages" | Out-Null
    nssm set $ServiceName Start SERVICE_AUTO_START | Out-Null
    
    nssm start $ServiceName | Out-Null
    Write-Host " -> Serviço $ServiceName instalado e iniciado!" -ForegroundColor Green
}

# Criar pasta de logs
if (-not (Test-Path "$RootDir\logs")) {
    New-Item -ItemType Directory -Path "$RootDir\logs" | Out-Null
}

# 1. API (Backend FastAPI)
Install-Service -ServiceName "IRAI_API" -AppDirectory $RootDir -AppParameters ""
nssm set "IRAI_API" Application "$RootDir\scripts\run_api.bat" | Out-Null

# 2. Worker Collector (Puxa os dados do MetaTrader e salva no DB)
Install-Service -ServiceName "IRAI_Collector" -AppDirectory $RootDir -AppParameters "backend\workers\collector.py --interval 60 --force"

# 3. Sincronizador Firebase (Puxa da API e manda pra Nuvem)
Install-Service -ServiceName "IRAI_FirebaseSync" -AppDirectory $RootDir -AppParameters ""
nssm set "IRAI_FirebaseSync" Application "$RootDir\scripts\run_firebase_sync.bat" | Out-Null

Write-Host ""
Write-Host "Tudo pronto! O IRAI agora roda 100% invisível e inicia com o Windows." -ForegroundColor Cyan
Write-Host "Você pode gerenciar os serviços abrindo o 'services.msc' no Windows." -ForegroundColor Yellow
