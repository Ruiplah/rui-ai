@echo off
chcp 65001 >nul
title Rui AI Launcher
cd /d D:\llama

echo ========================================
echo  Starting Rui AI...
echo ========================================

echo [1/2] Starting agent_server...
start "" /MIN "C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe" "D:\llama\agent_server.py"

echo [2/2] Starting llama-server (loading model ~30s)...
start "" /MIN "D:\llama\llama-server.exe" -m "D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf" -c 32768 --port 8080 --host 0.0.0.0 --path "D:\llama\webui"

echo.
echo Waiting for model load...
timeout /t 28 /nobreak >nul

echo.
echo Opening browser http://127.0.0.1:8080/ ...
start http://127.0.0.1:8080/

echo.
echo ========================================
echo Rui AI started!
echo Local: http://127.0.0.1:8080/
echo Phone(same WiFi): http://192.168.0.103:8080/
echo ========================================
timeout /t 4 /nobreak >nul

