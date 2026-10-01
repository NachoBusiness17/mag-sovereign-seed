@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Missing Mag venv. Run: powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\ensure_venv.ps1"
  exit /b 1
)
"%PY%" "%ROOT%main.py" %*
exit /b %ERRORLEVEL%