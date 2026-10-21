@echo off
REM 本地 AI 一键启动脚本：llama-server(8080) + agent_server(8082)
setlocal

set AGENT_PY=C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe

echo ========================================
echo   Rui AI 一键启动
echo ========================================
echo.

echo [1/2] 检查 llama-server (8080)...
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo   启动 llama-server（优化参数）...
  start "llama-server" "D:\llama\llama-server.exe" -m D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf -c 32768 --port 8080 --host 0.0.0.0 --path D:\llama\webui -ngl 99 -t 6 -tb 6 -fa on -ctk q4_0 -ctv q4_0 -ub 2048 --no-mmap
  echo   等待加载模型...
  timeout /t 10 /nobreak >nul
) else (
  echo   llama-server 已在运行
)

echo.
echo [2/2] 检查 agent_server (8082)...
netstat -ano | findstr ":8082" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo   启动 agent_server...
  start "agent-server" "%AGENT_PY%" D:\llama\agent_server.py
  timeout /t 3 /nobreak >nul
) else (
  echo   agent_server 已在运行
)

echo.
echo ========================================
echo   启动完成！
echo   电脑端：http://127.0.0.1:8080
echo   手机端：http://192.168.0.105:8080
echo ========================================
echo.
pause
