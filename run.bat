@echo off
setlocal
rem Windows Python fallback: installs Python and dependencies automatically.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_windows.ps1" %*
set "QR_EXIT=%ERRORLEVEL%"
if not "%QR_EXIT%"=="0" if not defined QRGENERATOR_NO_PAUSE pause
exit /b %QR_EXIT%
