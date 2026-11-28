@echo off
rem Optional install-only entry point. run.bat also installs before starting.
call "%~dp0run.bat" -PrepareOnly
exit /b %ERRORLEVEL%
