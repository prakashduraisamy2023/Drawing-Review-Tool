@echo off
setlocal
cd /d "%~dp0"

set "APP_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%APP_PYTHON%" (
  echo ERROR: Python environment was not found at .venv\Scripts\python.exe
  echo Create the virtual environment and install requirements.txt first.
  pause
  exit /b 1
)

"%APP_PYTHON%" -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo Installing Streamlit dependencies...
  "%APP_PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
  )
)

echo.
echo Engineering Drawing Intelligence is starting.
echo Local browser: http://127.0.0.1:8501
echo Other devices: use the Network URL printed by Streamlit below.
echo Keep this window open while the application is in use.
echo.

start "" "http://127.0.0.1:8501"
"%APP_PYTHON%" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
endlocal
