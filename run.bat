@echo off
title Sales Anomaly Studio
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "setup\start.ps1"
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo  Startup failed. The message above says why.
  echo  If it mentions the internet, connect and double-click again.
  echo ---------------------------------------------------------------
  echo.
  pause
)
