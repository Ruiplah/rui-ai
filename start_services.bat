@echo off
REM 本地 AI 一键启动脚本：llama-server(8080) + 代理服务(8082)
setlocal

set AGENT_PY=C:\Users\123\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe

echo 检查 llama-server (8080)...
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "llama-server" "D:\llama\llama-server.exe" -m D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf -c 8192 --port 8080 --host 127.0.0.1 --path D:\llama\webui -ngl 99 -t 12 -tb 12 -fa on -ctk q4_0 -ctv q4_0 -ub 1024
  echo 已启动 llama-server，等待加载模型...
) else (
  echo llama-server 已在运行
)

echo 检查代理服务 (8082)...
netstat -ano | findstr ":8082" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "agent-server" "%AGENT_PY%" D:\llama\agent_server.py
  echo 已启动代理服务
) else (
  echo 代理服务已在运行
)

echo.
echo 打开 http://127.0.0.1:8080 使用聊天界面
pause
