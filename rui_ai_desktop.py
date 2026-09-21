# -*- coding: utf-8 -*-
"""
Rui AI 桌面版启动器
功能：启动后端服务 + 打开桌面窗口，关闭窗口时自动清理后端进程
"""
import subprocess
import time
import sys
import os
import webview
import urllib.request

# ============ 配置 ============
LLAMA_SERVER = r"D:\llama\llama-server.exe"
MODEL_PATH = r"D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf"
WEBUI_DIR = r"D:\llama\webui"
AGENT_SERVER = r"D:\llama\agent_server.py"
PYTHON_EXE = sys.executable

# 服务端口
LLAMA_PORT = 8080
AGENT_PORT = 8082

# 启动参数（和 start_services.bat 保持一致）
LLAMA_ARGS = [
    "-m", MODEL_PATH,
    "-c", "8192",
    "--port", str(LLAMA_PORT),
    "--host", "127.0.0.1",
    "--path", WEBUI_DIR,
    "-ngl", "99",
    "-t", "12",
    "-tb", "12",
]

# ============ 进程管理 ============
llama_proc = None
agent_proc = None


def is_port_in_use(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_service(port, timeout=60):
    """等待服务就绪"""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(1)
    return False


def start_backends():
    """启动两个后端服务"""
    global llama_proc, agent_proc

    # 启动 llama-server
    if not is_port_in_use(LLAMA_PORT):
        print("[启动] llama-server (8080)...")
        llama_proc = subprocess.Popen(
            [LLAMA_SERVER] + LLAMA_ARGS,
            cwd=r"D:\llama",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        print("[跳过] llama-server 已在运行")

    # 启动 agent_server
    if not is_port_in_use(AGENT_PORT):
        print("[启动] agent_server (8082)...")
        agent_proc = subprocess.Popen(
            [PYTHON_EXE, AGENT_SERVER],
            cwd=r"D:\llama",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        print("[跳过] agent_server 已在运行")

    # 等待 llama-server 加载模型
    print("[等待] llama-server 加载模型...")
    if wait_for_service(LLAMA_PORT, timeout=120):
        # 再等几秒确保模型加载完成
        time.sleep(3)
        print("[就绪] llama-server")
    else:
        print("[警告] llama-server 启动超时")

    if wait_for_service(AGENT_PORT, timeout=15):
        print("[就绪] agent_server")
    else:
        print("[警告] agent_server 启动超时")


def stop_backends():
    """关闭后端进程（仅关闭自己启动的）"""
    global llama_proc, agent_proc

    if llama_proc and llama_proc.poll() is None:
        print("[清理] 停止 llama-server...")
        llama_proc.terminate()
        try:
            llama_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            llama_proc.kill()

    if agent_proc and agent_proc.poll() is None:
        print("[清理] 停止 agent_server...")
        agent_proc.terminate()
        try:
            agent_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            agent_proc.kill()


def on_closed():
    """窗口关闭回调"""
    stop_backends()


# ============ 主入口 ============
if __name__ == "__main__":
    print("=" * 50)
    print("  Rui AI 桌面版")
    print("=" * 50)

    # 启动后端
    start_backends()

    # 打开桌面窗口
    print("[打开] 桌面窗口...")
    window = webview.create_window(
        title="Rui AI",
        url=f"http://127.0.0.1:{LLAMA_PORT}/",
        width=1280,
        height=800,
        min_size=(900, 600),
        background_color="#1a1a2e",
    )

    # 绑定关闭事件
    window.events.closed += on_closed

    # 启动 GUI
    webview.start(debug=False)
