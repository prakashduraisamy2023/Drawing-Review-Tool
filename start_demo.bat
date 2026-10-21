@echo off
setlocal
cd /d "%~dp0"

set "DEMO_PYTHON=%CD%\.venv\Scripts\python.exe"
set "DEMO_URL=http://127.0.0.1:8000"

if not exist "%DEMO_PYTHON%" (
  echo ERROR: Python environment was not found at .venv\Scripts\python.exe
  echo Install the backend dependencies before starting the demonstration.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo ERROR: The production frontend is missing and npm is not available.
    echo Install Node.js, run npm install in frontend, then run npm run build.
    pause
    exit /b 1
  )
  echo Building the production frontend...
  pushd frontend
  call npm run build
  if errorlevel 1 (
    popd
    echo ERROR: Frontend build failed. Review the messages above.
    pause
    exit /b 1
  )
  popd
)

echo Starting Engineering Drawing Intelligence at %DEMO_URL% ...
set "DRAWING_DEMO_MODE=true"
set "DRAWING_LEVEL3_ENABLED=true"
set "DRAWING_LEVEL4_ENABLED=true"
start "Engineering Drawing Intelligence" /B "%DEMO_PYTHON%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

powershell.exe -NoProfile -Command "$ready=$false; 1..30 | ForEach-Object { try { $response=Invoke-WebRequest -UseBasicParsing '%DEMO_URL%/health' -TimeoutSec 1; if ($response.StatusCode -eq 200) { $ready=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if (-not $ready) { exit 1 }"
if errorlevel 1 (
  echo ERROR: The local server did not become healthy within 15 seconds.
  echo Check whether port 8000 is already in use and review the server output.
  pause
  exit /b 1
)

start "" "%DEMO_URL%"
echo Demo ready. Close this window to leave the background server running.
endlocal
