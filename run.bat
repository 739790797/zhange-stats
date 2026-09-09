@echo off
rem Start this install tree (backend :6130, frontend :6131).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\win\run.ps1"
if errorlevel 1 pause
