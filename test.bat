@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\check.py
if errorlevel 1 (
  echo Tests failed. See test-results for details.
  exit /b 1
)
echo All regression and E2E checks passed.
