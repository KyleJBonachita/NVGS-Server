@echo off
title DownloadServer
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo Node.js was not found.
  echo Install Node.js 20 or newer, then run this file again.
  echo.
  pause
  exit /b 1
)

node server.js

if errorlevel 1 (
  echo.
  echo DownloadServer stopped because of an error.
  pause
)
