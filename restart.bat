@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\win\restart.ps1"
if errorlevel 1 pause
