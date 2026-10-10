@echo off
rem ImpactProof demo launcher: starts both field devices and opens everything in the browser.
rem The Qdrant key is read from field\data\qdrant.key (field\data is never committed to Git).
cd /d "%~dp0"

if not exist "field\data\qdrant.key" (
  echo Missing field\data\qdrant.key - put your Qdrant Cloud API key in that file first.
  pause
  exit /b 1
)
set /p QKEY=<field\data\qdrant.key
set QURL=https://318a8550-7cc8-46fa-beba-08c02d006412.sa-east-1-0.aws.cloud.qdrant.io:6333
set HQ=https://impactproof-api.onrender.com

echo Waking up ImpactProof HQ...
start "" https://impactproof-web.onrender.com/api/ping

start "Disha's device (8101)" cmd /k .venv-field\Scripts\python.exe -m field --device disha --name "Disha's phone" --port 8101 --https --hq %HQ% --project 1 --qdrant %QURL% --qdrant-key %QKEY%
start "Ravi's device (8102)" cmd /k .venv-field\Scripts\python.exe -m field --device ravi --name "Ravi's phone" --port 8102 --https --hq %HQ% --project 1 --qdrant %QURL% --qdrant-key %QKEY%

echo Loading the on-device AI models (about 30 seconds)...
timeout /t 35 /nobreak >nul
start "" https://localhost:8101
start "" https://localhost:8102
start "" https://impactproof-web.onrender.com/dashboard
echo Ready. Leave the two device windows open.
