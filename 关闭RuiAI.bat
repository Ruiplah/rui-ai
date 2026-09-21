@echo off
chcp 65001 >nul
title Rui AI Stopper

echo ========================================
echo  Stopping Rui AI...
echo ========================================

echo Stopping llama-server...
taskkill /F /IM llama-server.exe 2>nul

echo Stopping agent_server...
taskkill /F /IM python.exe 2>nul

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo Rui AI stopped
echo ========================================
timeout /t 3 /nobreak >nul
