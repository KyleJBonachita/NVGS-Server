@echo off
setlocal
title NVGS Client Setup

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-nvgs-windows.ps1"
set "setup_status=%errorlevel%"

if not "%setup_status%"=="0" (
  echo.
  echo NVGS Client Setup did not complete.
  echo No password or NVIDIA login information was collected.
  echo.
  pause
)

exit /b %setup_status%
