@echo off
chcp 65001 >nul
title Rui AI 桌面版
cd /d D:\llama

REM 使用和 start_services.bat 相同的 Python
set PYTHON=C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe

echo 正在启动 Rui AI 桌面版...
start "" "%PYTHON%" "D:\llama\rui_ai_desktop.py"
exit
