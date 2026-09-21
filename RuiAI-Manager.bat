@echo off
chcp 65001 >nul
title Rui AI 服务管理器

set LLAMA_SERVER=D:\llama\llama-server.exe
set MODEL_PATH=D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf
set AGENT_SERVER=D:\llama\agent_server.py
set PYTHON_PATH=C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe
set WEBUI_PATH=D:\llama\webui
set LLAMA_PORT=8080
set AGENT_PORT=8082

if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status
if "%1"=="health" goto health

echo Rui AI 服务管理器
echo 用法: RuiAI-Manager.bat [start^|stop^|restart^|status^|health]
echo.
echo   start   - 启动所有服务
echo   stop    - 停止所有服务
echo   restart - 重启所有服务
echo   status  - 查看服务状态
echo   health  - 健康检查
echo.
goto end

:start
echo ========================================
echo 启动 Rui AI 服务...
echo ========================================

echo [1/2] 启动 agent_server (端口 %AGENT_PORT%)...
start "" /B "%PYTHON_PATH%" "%AGENT_SERVER%"
timeout /t 3 /nobreak >nul

echo [2/2] 启动 llama-server (端口 %LLAMA_PORT%)...
start "" /B "%LLAMA_SERVER%" -m "%MODEL_PATH%" -c 16384 --port %LLAMA_PORT% --host 0.0.0.0 --path "%WEBUI_PATH%"
echo 等待模型加载（约30秒）...
timeout /t 30 /nobreak >nul

echo.
call :health
echo ========================================
echo Rui AI 启动完成！
echo 本机访问: http://127.0.0.1:%LLAMA_PORT%/
echo 局域网访问: http://192.168.0.103:%LLAMA_PORT%/ （手机需连同一WiFi）
echo ========================================
goto end

:stop
echo ========================================
echo 停止 Rui AI 服务...
echo ========================================

echo 停止 llama-server...
taskkill /F /IM llama-server.exe 2>nul
echo 停止 agent_server (python)...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo 所有服务已停止
goto end

:restart
echo 重启 Rui AI 服务...
call :stop
timeout /t 3 /nobreak >nul
call :start
goto end

:status
echo ========================================
echo 服务状态
echo ========================================

echo.
echo [进程状态]
tasklist /FI "IMAGENAME eq llama-server.exe" 2>nul | findstr /I "llama-server" >nul && echo llama-server: 运行中 || echo llama-server: 未运行
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python" >nul && echo agent_server(python): 运行中 || echo agent_server(python): 未运行

echo.
echo [端口状态]
netstat -ano | findstr ":%LLAMA_PORT% " >nul && echo 端口 %LLAMA_PORT% (llama-server): 已监听 || echo 端口 %LLAMA_PORT% (llama-server): 未监听
netstat -ano | findstr ":%AGENT_PORT% " >nul && echo 端口 %AGENT_PORT% (agent_server): 已监听 || echo 端口 %AGENT_PORT% (agent_server): 未监听
goto end

:health
echo ========================================
echo 健康检查
echo ========================================

echo.
echo [llama-server]
curl -s -m 5 http://127.0.0.1:%LLAMA_PORT%/health >nul 2>&1 && echo 状态: 正常 (http://127.0.0.1:%LLAMA_PORT%/health) || echo 状态: 异常 (无法连接)

echo.
echo [agent_server]
curl -s -m 5 http://127.0.0.1:%AGENT_PORT%/health >nul 2>&1 && echo 状态: 正常 (http://127.0.0.1:%AGENT_PORT%/health) || echo 状态: 异常 (无法连接)
goto end

:end
