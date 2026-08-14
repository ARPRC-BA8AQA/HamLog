@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment. Install Python 3.9+ first.
    exit /b 1
  )
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not defined HAMLOG_AES_KEY (
  echo Warning: HAMLOG_AES_KEY is not set. A development key may be stored in data\secret.key.
)
.venv\Scripts\python.exe run.py
