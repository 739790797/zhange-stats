@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Double-click = start. Or: run_dev.bat stop^|restart^|status
set "ARGS=%*"
if "%~1"=="" set "ARGS=start"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %ARGS%
set "ERR=%ERRORLEVEL%"

if "%~1"=="" (
  echo.
  if not "%ERR%"=="0" echo Start failed. See .dev\*.err.log
  pause
)
exit /b %ERR%
