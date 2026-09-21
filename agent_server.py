#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 AI 代理服务（搜索 + 网页抓取 + 工具执行）
监听 127.0.0.1:8082
  GET  /health                    健康检查
  GET  /api/search?q=..&n=..      联网搜索
  GET  /api/fetch?url=..          抓取网页正文
  POST /api/exec                  执行工具（带安全护栏）
"""
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import ssl
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import traceback
import threading
import queue
import time
import sys

_OCR_ENGINE = None   # RapidOCR 懒加载单例

# ===== 飞书配置（在飞书开放平台创建自建应用后填入） =====
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")            # 从环境变量读取，勿硬编码
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")    # 从环境变量读取，勿硬编码；为空时飞书功能返回提示
_feishu_token = {"token": "", "expire": 0}  # tenant_access_token 缓存

HOST = "0.0.0.0"
PORT = 8082
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUI_STATE_DIR = r"D:\llama\rui_state"
_VALID_KEY = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")

# ===== 安全加固：文件访问白名单（防路径遍历） =====
import tempfile as _tempfile
ALLOWED_DIRS = [
    os.path.realpath(r"D:\llama"),
    os.path.realpath(os.path.join(os.path.expanduser("~"), "Downloads")),
    os.path.realpath(os.path.join(os.path.expanduser("~"), "Desktop")),
    os.path.realpath(os.path.join(os.path.expanduser("~"), "Documents")),
    os.path.realpath(_tempfile.gettempdir()),
]
def _is_path_allowed(p):
    """检查路径是否在白名单目录内（realpath规范化后比对，防 ../ 遍历）"""
    try:
        real = os.path.realpath(p)
        return any(real == d or real.startswith(d + os.sep) for d in ALLOWED_DIRS)
    except Exception:
        return False

# ===== 安全加固：访问Token（设置环境变量 RUI_ACCESS_TOKEN 则启用，未设置不强制） =====
ACCESS_TOKEN = os.environ.get("RUI_ACCESS_TOKEN", "").strip()

# ---------- 模型切换 ----------
LLAMA_SERVER = r"D:\llama\llama-server.exe"
LLAMA_PORT = 8080
LLAMA_CTX = 8192  # 8K上下文：平衡速度与内存，避免16K导致虚拟内存拖慢速度
WEBUI_PATH = r"D:\llama\webui"
MODELS = {
    "qwen3.5-9b": {
        "name": "Qwen3.5-9B (Q4_K_M)",
        "path": r"D:\llama\models\Qwen_Qwen3.5-9B-Q4_K_M.gguf",
        "thinking": True,   # Qwen3.5 支持思考模式
    },
    "deepseek-r1-7b": {
        "name": "DeepSeek-R1-Distill-Qwen-7B (Q4_K_M)",
        "path": r"D:\llama\models\DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "thinking": True,   # DeepSeek R1 始终思考
    },
    "gemma-4-12b": {
        "name": "Gemma 4 12B (Q4_K_M)",
        "path": r"D:\llama\models\gemma-4-12B-it-Q4_K_M.gguf",
        "thinking": False,  # Gemma 4 带思考通道，必须关闭否则输出空白/夹杂推敲
    },
}

def list_models():
    available = {}
    for k, v in MODELS.items():
        available[k] = {"name": v["name"], "path": v["path"], "exists": os.path.isfile(v["path"]), "thinking": v.get("thinking", True)}
    current = None
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{LLAMA_PORT}/v1/models")
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            mid = data.get("data", [{}])[0].get("id", "")
            for k, v in MODELS.items():
                if v["path"] in mid or k in mid.lower():
                    current = k
                    break
            if not current:
                current = mid
    except Exception:
        current = None
    return {"models": available, "current": current}

def switch_model(model_key):
    if model_key not in MODELS:
        return {"ok": False, "error": f"未知模型: {model_key}", "available": list(MODELS.keys())}
    info = MODELS[model_key]
    model_path = info["path"]
    if not os.path.isfile(model_path):
        return {"ok": False, "error": f"模型文件不存在: {model_path}"}
    # 停止当前 llama-server
    try:
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                       capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass
    time.sleep(2)
    # 确认已停止
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{LLAMA_PORT}/health", timeout=1)
        return {"ok": False, "error": "无法停止旧模型服务，请手动关闭 llama-server.exe"}
    except Exception:
        pass  # 预期：连接失败说明已停止
    # 启动新模型
    try:
        subprocess.Popen([
            LLAMA_SERVER,
            "-m", model_path,
            "-c", str(LLAMA_CTX),
            "--port", str(LLAMA_PORT),
            "--host", "0.0.0.0",  # 允许局域网（手机）访问，与手动启动命令一致
            "--path", WEBUI_PATH,
            "-ngl", "99",       # GPU加速：全部层卸载到显存（8GB显存可放下12B Q4模型）
            "-t", "12",          # CPU线程：i5-10600KF有12逻辑处理器
            "-tb", "12",         # batch线程：prefill阶段也用12线程
        ], creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        return {"ok": False, "error": f"启动失败: {e}"}
    # 等待健康检查
    for i in range(60):
        time.sleep(2)
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{LLAMA_PORT}/health")
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    return {"ok": True, "model": model_key, "name": info["name"],
                            "ready_after": f"{(i+1)*2}s"}
        except Exception:
            continue
    return {"ok": False, "error": "模型启动超时（120秒），请检查日志"}

# ---------- 联网 ----------
def http_get(url, timeout=15):
    # 根据域名选择不同的请求头，避免被反爬虫
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    # 搜狗搜索专用请求头
    if "sogou.com" in url:
        headers["Referer"] = "https://www.sogou.com/"
    # 360搜索专用请求头
    elif "so.com" in url:
        headers["Referer"] = "https://www.so.com/"
    # Bing专用请求头
    elif "bing.com" in url:
        headers["Referer"] = "https://www.bing.com/"
    # 液体百科专用请求头
    elif "liquipedia" in url:
        headers["Referer"] = "https://liquipedia.net/"
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    # 默认启用SSL证书校验；自签名网站失败时降级一次（禁用校验重试）
    def _http_fetch(verify):
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read()
    try:
        data = _http_fetch(True)
    except ssl.SSLError:
        data = _http_fetch(False)  # 自签名证书降级重试
        # 1. 从响应头获取 charset
        charset = r.headers.get_content_charset()
        # 2. 从 HTML meta 标签检测（更可靠）
        try:
            head = data[:3000].decode("ascii", errors="ignore")
            m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
            if m:
                detected = m.group(1).lower()
                # 只在响应头没有或者检测到gbk/gb2312时使用检测结果
                if not charset or detected in ["gbk", "gb2312", "gb18030"]:
                    charset = detected
        except Exception:
            pass
        # 3. 默认 utf-8
        if not charset:
            charset = "utf-8"
        # 4. 尝试解码，失败则依次尝试 gbk 和 utf-8
        for enc in [charset, "gbk", "gb18030", "utf-8"]:
            try:
                return data.decode(enc, errors="replace")
            except Exception:
                continue
        return data.decode("utf-8", errors="replace")

def strip_html(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()

# 搜索缓存（避免频繁请求被反爬虫，线程安全+LRU上限）
import threading as _st
_search_cache_lock = _st.Lock()
_search_cache = {}
_search_cache_time = {}
_SEARCH_CACHE_MAX = 200
_baidu_cookie = {"value": "", "time": 0}  # 百度首页cookie缓存，避免每次搜索都多一次请求

def search(q, n=12):
    """四源并发搜索：360 + 百度 + Bing + B站；单源8s超时、整体15s上限；相关性排序；发布时间提取"""
    global _search_cache, _search_cache_time, _baidu_cookie
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_key = q.strip().lower()
    now = time.time()
    with _search_cache_lock:
        if cache_key in _search_cache and now - _search_cache_time.get(cache_key, 0) < 300:
            return _search_cache[cache_key][:n]

    # 提取核心关键词：只删句尾语气词和双字疑问短语，不删单字（保护"我的世界/几米/的确良"等专有名词）
    def extract_keywords(query):
        k = query.strip()
        k = re.sub(r"[吗呢吧啊呀？?]+$", "", k).strip()  # 仅句尾语气词/问号
        for w in ["是谁", "是什么", "怎么样", "怎么", "如何", "为什么", "为何", "哪里", "哪儿",
                  "什么时候", "何时", "多少", "介绍一下", "告诉我", "请问", "帮我查", "搜索", "查找", "查询"]:
            k = k.replace(w, "")
        return k.strip()

    keyword = extract_keywords(q) or q

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def fetch_html(url, headers, timeout=8):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            charset = r.headers.get_content_charset()
            if not charset:
                head = data[:2000].decode("ascii", errors="ignore")
                m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
                if m:
                    charset = m.group(1).lower()
            for enc in [charset, "utf-8", "gbk", "gb18030"]:
                if not enc:
                    continue
                try:
                    return data.decode(enc, errors="replace")
                except Exception:
                    continue
            return data.decode("utf-8", errors="replace")

    # 发布时间提取：在结果块附近搜日期/相对时间
    def _date_near(html, pos, span=2500):
        seg = html[pos:pos + span]
        m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)", seg)
        if m:
            return m.group(1)
        m = re.search(r"(\d+)\s*(天|小时|分钟)前", seg)
        if m:
            return m.group(0)
        if "昨天" in seg:
            return "昨天"
        if "今天" in seg:
            return "今天"
        return ""

    # ---- 各源独立函数（不共享可变状态，并发执行）----
    def src_360():
        out = []
        try:
            url = "https://www.so.com/s?q=" + urllib.parse.quote(keyword)
            html = fetch_html(url, {"User-Agent": UA, "Referer": "https://www.so.com/", "Accept-Language": "zh-CN,zh;q=0.9"})
            for hm in re.finditer(r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
                title = re.sub(r"<[^>]+>", "", hm.group(2)).strip()
                u = hm.group(1).strip()
                if u.startswith("/"):
                    u = "https://www.so.com" + u
                if not title or len(title) < 2 or not u:
                    continue
                sm = re.search(r"<p[^>]*>(.*?)</p>", html[hm.end():hm.end() + 1500], re.S | re.I)
                snippet = re.sub(r"<[^>]+>", "", sm.group(1)).strip() if sm else ""
                out.append({"title": title, "url": u, "snippet": snippet, "source": "360", "date": _date_near(html, hm.end())})
                if len(out) >= 5:
                    break
        except Exception:
            pass
        return out

    def src_baidu():
        out = []
        try:
            # cookie缓存300秒，避免每次搜索都先访问首页（省一次5s往返）
            if not _baidu_cookie["value"] or now - _baidu_cookie["time"] > 300:
                req0 = urllib.request.Request("https://www.baidu.com/", headers={"User-Agent": UA})
                resp0 = urllib.request.urlopen(req0, timeout=5)
                cookie_str = resp0.headers.get("Set-Cookie", "")
                _baidu_cookie["value"] = "; ".join([c.split(";")[0] for c in cookie_str.split(",") if c.strip()])[:300]
                _baidu_cookie["time"] = now
            url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(keyword)
            html = fetch_html(url, {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Cookie": _baidu_cookie["value"]})
            if "安全验证" not in html and "wappass" not in html:
                for hm in re.finditer(r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
                    title = re.sub(r"<[^>]+>", "", hm.group(2)).strip()
                    u = hm.group(1).strip()
                    if u.startswith("//"):
                        u = "https:" + u
                    if not title or len(title) < 2:
                        continue
                    sm = re.search(r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</div>', html[hm.end():hm.end() + 2500], re.S | re.I)
                    snippet = re.sub(r"<[^>]+>", "", sm.group(1)).strip() if sm else ""
                    out.append({"title": title, "url": u, "snippet": snippet, "source": "百度", "date": _date_near(html, hm.end())})
                    if len(out) >= 5:
                        break
        except Exception:
            pass
        return out

    def src_bing():
        out = []
        try:
            url = "https://cn.bing.com/search?q=" + urllib.parse.quote(keyword) + "&count=15&setlang=zh-CN"
            html = fetch_html(url, {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
            for hm in re.finditer(r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
                title = re.sub(r"<[^>]+>", "", hm.group(2)).strip()
                u = hm.group(1)
                if any(x in u for x in ["bing.com", "microsoft.com", "go.microsoft", "msn.com"]):
                    continue
                pm = re.search(r"<p[^>]*>(.*?)</p>", html[hm.end():hm.end() + 2000], re.S | re.I)
                snippet = re.sub(r"<[^>]+>", "", pm.group(1)).strip() if pm else ""
                out.append({"title": title, "url": u, "snippet": snippet, "source": "Bing", "date": _date_near(html, hm.end())})
                if len(out) >= 3:
                    break
        except Exception:
            pass
        return out

    def src_bilibili():
        out = []
        try:
            url = "https://search.bilibili.com/all?keyword=" + urllib.parse.quote(keyword)
            html = fetch_html(url, {"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"})
            seen_b = set()
            for vm in re.finditer(r'<a[^>]+href="(//www\.bilibili\.com/video/BV[^"]+)"[^>]*title="([^"]{4,80})"', html):
                u = "https:" + vm.group(1)
                title = vm.group(2).strip()
                if title in seen_b:
                    continue
                seen_b.add(title)
                out.append({"title": title, "url": u, "snippet": "", "source": "B站", "date": ""})
                if len(out) >= 4:
                    break
        except Exception:
            pass
        return out

    # 四源并发，整体15秒上限
    all_results = []
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(fn): fn.__name__ for fn in [src_360, src_baidu, src_bing, src_bilibili]}
            for fut in as_completed(futures, timeout=15):
                try:
                    all_results.extend(fut.result(timeout=2))
                except Exception:
                    pass
    except Exception:
        pass

    # 合并去重（url + title）
    final = []
    seen_url, seen_title = set(), set()
    for r in all_results:
        if r["url"] in seen_url or r["title"] in seen_title:
            continue
        seen_url.add(r["url"])
        seen_title.add(r["title"])
        final.append(r)

    # 相关性排序：query字符与title+snippet重合度 + 域名权威度加权
    q_chars = set(re.sub(r"\s+", "", keyword))
    def _score(item):
        text = re.sub(r"\s+", "", item["title"] + " " + item.get("snippet", ""))
        t_chars = set(text)
        overlap = len(q_chars & t_chars) / max(len(q_chars), 1)
        if any(d in item["url"] for d in ["baike.", "wiki.", "gov.cn", "edu.cn", "zhihu.com"]):
            authority = 0.15
        elif "baidu.com" in item["url"]:
            authority = 0.05
        else:
            authority = 0
        return overlap + authority
    final.sort(key=_score, reverse=True)

    with _search_cache_lock:
        # LRU：超过上限删除最旧
        if len(_search_cache) >= _SEARCH_CACHE_MAX:
            oldest = min(_search_cache_time, key=_search_cache_time.get)
            del _search_cache[oldest]
            del _search_cache_time[oldest]
        _search_cache[cache_key] = final
        _search_cache_time[cache_key] = now
    return final[:n]
# ==================== 飞书多维表格 ====================
def feishu_get_token():
    """获取 tenant_access_token（带缓存，提前 60 秒刷新）"""
    global _feishu_token
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        return None
    now = time.time()
    if _feishu_token["token"] and now < _feishu_token["expire"] - 60:
        return _feishu_token["token"]
    try:
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("code") == 0:
            _feishu_token["token"] = data["tenant_access_token"]
            _feishu_token["expire"] = now + data.get("expire", 7200)
            return _feishu_token["token"]
        return None
    except Exception:
        return None

def feishu_api(method, path, token, body=None):
    """通用飞书 API 调用"""
    url = "https://open.feishu.cn/open-apis" + path
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": -1, "msg": "HTTP " + str(e.code)}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

def ps_run(script, timeout=40):
    """执行 PowerShell 脚本，返回 stdout/stderr/returncode"""
    try:
        ps = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]
        r = subprocess.run(ps, capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        class R:
            pass
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return type("PSResult", (), {"stdout": out, "stderr": err, "returncode": r.returncode})
    except Exception as e:
        return type("PSResult", (), {"stdout": "", "stderr": str(e), "returncode": -1})

def _need(tool, message, params):
    """返回需要用户确认的信号，前端弹窗后带 confirmed 重发"""
    return {"need_confirm": True, "tool": tool, "message": message, "params": params or {}}

def safe_calc(expr):
    """安全数学表达式计算（仅允许基本运算和常用数学函数）"""
    import math
    allowed_names = {"abs","min","max","round","sum","len","int","float","str","pow",
                     "sqrt","log","log10","exp","sin","cos","tan","pi","e","floor","ceil"}
    def check(node):
        if isinstance(node, ast.Expression):
            return check(node.body)
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (int, float))
        if isinstance(node, ast.BinOp):
            return check(node.left) and check(node.right)
        if isinstance(node, ast.UnaryOp):
            return check(node.operand)
        if isinstance(node, ast.Call):
            return (isinstance(node.func, ast.Name) and node.func.id in allowed_names
                    and all(check(a) for a in node.args))
        if isinstance(node, ast.Name):
            return node.id in ("pi", "e")
        return False
    tree = ast.parse(expr, mode="eval")
    if not check(tree):
        raise ValueError("表达式包含不允许的操作")
    ns = {"__builtins__": {}, "abs":abs, "min":min, "max":max, "round":round, "sum":sum,
          "len":len, "int":int, "float":float, "str":str, "pow":pow, "sqrt":math.sqrt,
          "log":math.log, "log10":math.log10, "exp":math.exp, "sin":math.sin, "cos":math.cos,
          "tan":math.tan, "pi":math.pi, "e":math.e, "floor":math.floor, "ceil":math.ceil}
    return eval(compile(tree, "<safe>", "eval"), ns)

def run_command(cmd, confirmed=False, timeout=30, background=False):
    """执行系统命令；危险命令需用户确认后带 confirmed=True 执行"""
    if not confirmed:
        return _need("run_command", "执行命令：\n" + str(cmd)[:200], {"cmd": cmd, "timeout": timeout})
    # 服务端危险命令黑名单（纵深防御：即使前端确认了，也拦截不可逆操作）
    _cmd_lower = str(cmd).lower()
    _dangerous = [
        r"\bformat\s", r"\bfdisk\b", r"\bdel\s+[^\n]*/s\b", r"\brmdir\s+[^\n]*/s\b",
        r"\breg\s+(add|delete)\b", r"\bshutdown\s+/s\b", r"\bcipher\s+/w\b",
        r"\btakeown\b", r"\bicacls\s+[^\n]*/grant\s+[^\n]*everyone",
    ]
    for _pat in _dangerous:
        if re.search(_pat, _cmd_lower):
            return {"error": "命令被安全策略拦截（不可逆/高风险操作）：" + str(cmd)[:120]}
    # 强制限制超时：最多30秒，防止模型传大timeout导致卡死
    safe_timeout = min(max(int(timeout or 30), 5), 30)
    try:
        # Windows 上用 Popen + 进程树终止，确保超时后子进程也被杀掉
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=CREATE_NO_WINDOW)
        try:
            stdout, stderr = proc.communicate(timeout=safe_timeout)
            out = stdout.decode("utf-8", errors="replace")[:20000] if stdout else ""
            err = stderr.decode("utf-8", errors="replace")[:20000] if stderr else ""
            return {"ok": proc.returncode == 0, "exit": proc.returncode, "stdout": out, "stderr": err}
        except subprocess.TimeoutExpired:
            # 超时后终止整个进程树
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                             capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=5)
            except Exception:
                try: proc.kill()
                except Exception: pass
            return {"error": "命令执行超时（" + str(safe_timeout) + "秒），已强制终止"}
    except Exception as e:
        return {"error": "命令执行失败：" + str(e)[:300]}

def fetch_text(url, max_len=20000):
    """抓取网页正文纯文本：优先 article/main 三级定位，减少导航/广告噪音"""
    try:
        html = http_get(url, timeout=20)
        # 提取 title
        tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = strip_html(tm.group(1)) if tm else ""
        # 三级正文定位：article > main > body
        body = ""
        for tag in ["article", "main"]:
            mm = re.search(r"<" + tag + r"[^>]*>.*?</" + tag + r">", html, re.S | re.I)
            if mm:
                body = mm.group(0)
                break
        if not body:
            mm = re.search(r"<body[^>]*>.*?</body>", html, re.S | re.I)
            if mm:
                body = mm.group(0)
        text = strip_html(body) if body else strip_html(html)
        text = re.sub(r"\s+", " ", text).strip()
        truncated = len(text) > max_len
        if truncated:
            text = text[:max_len] + "……（内容过长已截断）"
        return {"ok": True, "url": url, "title": title, "text": text, "chars": min(len(text), max_len), "truncated": truncated}
    except Exception as e:
        return {"error": "抓取失败：" + str(e)[:300]}

def read_doc(path, meta_only=False):
    """读取 Word/Excel/CSV/PDF/文本文件内容"""
    if not os.path.exists(path):
        return {"error": "文件不存在：" + path}
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            rows_all = []
            for ws in wb.worksheets:
                rows_all.append("【工作表：" + ws.title + "】")
                for row in ws.iter_rows(values_only=True):
                    vals = ["" if v is None else str(v) for v in row]
                    if any(v.strip() for v in vals):
                        rows_all.append(" | ".join(vals))
            wb.close()
            text = "\n".join(rows_all)[:100000]
            return {"ok": True, "path": path, "content": text, "chars": len(text), "type": "excel"}
        if ext == ".csv":
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()[:100000]
            return {"ok": True, "path": path, "content": text, "chars": len(text), "type": "csv"}
        if ext == ".docx":
            import zipfile as _zipfile
            with _zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            text = re.sub(r"<w:p[ >]", "\n", xml)
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\n{2,}", "\n", text).strip()
            return {"ok": True, "path": path, "content": text[:100000], "chars": len(text), "type": "word"}
        if ext == ".pdf":
            try:
                with open(path, "rb") as f:
                    data = f.read()
                # 简单文本提取（无pypdf时用正则抓流式文本）
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(path)
                    text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
                except Exception:
                    text = re.sub(rb"\([()])", b"\1", data).decode("latin1", errors="replace")
                    text = re.sub(r"[^\x20-\x7e\u4e00-\u9fff\n]", " ", text)
            except Exception:
                text = ""
            return {"ok": True, "path": path, "content": text[:100000], "chars": len(text), "type": "pdf"}
        # 其他按文本处理
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()[:100000]
        return {"ok": True, "path": path, "content": text, "chars": len(text), "type": "text"}
    except Exception as e:
        return {"error": "读取失败：" + str(e)[:300]}

def create_doc(path, content):
    """创建 Word 文档(.docx)，优先 python-docx，缺失时手工构造 docx"""
    if isinstance(content, str) and content.startswith("__confirmed__"):
        content = content[len("__confirmed__"):]
    if not path.lower().endswith(".docx"):
        path = path + ".docx"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    try:
        try:
            import docx
            from docx import Document
            d = Document()
            for para in str(content).split("\n"):
                d.add_paragraph(para)
            d.save(path)
        except ImportError:
            import zipfile as _zipfile
            esc = lambda t: (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            paras = "".join(
                '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % esc(p)
                for p in str(content).split("\n"))
            document_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>%s</w:body></w:document>') % paras
            content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>')
            rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>')
            with _zipfile.ZipFile(path, "w", _zipfile.ZIP_DEFLATED) as z:
                z.writestr("[Content_Types].xml", content_types)
                z.writestr("_rels/.rels", rels)
                z.writestr("word/document.xml", document_xml)
        return {"ok": True, "path": path, "chars": len(str(content)), "type": "docx"}
    except Exception as e:
        return {"error": "创建文档失败：" + str(e)[:300]}

def stat_data(params):
    """统计分析 Excel/CSV：按某列分组，对另一列做 sum/count/avg"""
    path = params.get("path", "")
    group_by = params.get("group_by", "")
    agg_col = params.get("agg_col", "")
    agg = params.get("agg", "count")
    if not path or not os.path.exists(path):
        return {"error": "文件不存在：" + path}
    try:
        rows_all = []
        if path.lower().endswith((".xlsx", ".xlsm")):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            for row in wb.active.iter_rows(values_only=True):
                rows_all.append(list(row))
            wb.close()
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    rows_all.append(line.rstrip("\n").split(","))
        if not rows_all:
            return {"error": "空表"}
        headers = [str(h) if h is not None else "" for h in rows_all[0]]
        data = rows_all[1:]
        gi = headers.index(group_by) if group_by in headers else None
        ai = headers.index(agg_col) if agg_col in headers else None
        if gi is None:
            return {"error": "找不到分组列：" + str(group_by) + "。可用列：" + "、".join(headers)}
        groups = {}
        for row in data:
            if len(row) <= gi:
                continue
            gkey = str(row[gi] or "空")
            val = row[ai] if (ai is not None and ai < len(row)) else 1
            groups.setdefault(gkey, []).append(val)
        def to_num(x):
            try:
                return float(x)
            except Exception:
                return None
        result = []
        for g, vals in groups.items():
            nums = [n for n in (to_num(v) for v in vals) if n is not None]
            if agg == "sum":
                v = round(sum(nums), 4) if nums else 0
            elif agg == "avg":
                v = round(sum(nums) / len(nums), 4) if nums else 0
            else:
                v = len(vals)
            result.append({group_by: g, (agg + "_" + (agg_col or "计数")): v})
        return {"ok": True, "headers": headers, "rows": result, "count": len(result),
                "agg": agg, "group_by": group_by, "agg_col": agg_col}
    except Exception as e:
        return {"error": "统计失败：" + str(e)[:300]}


# ---------- 浏览器自动化（Playwright，专用工作线程） ----------
class BrowserManager:
    """Playwright 的 sync API 绑定创建它的线程；而 ThreadingHTTPServer 每个请求换线程，
    直接跨请求操作会报 'cannot switch to a different thread'。
    解决：所有 Playwright 操作都提交到唯一的 browser-worker 线程串行执行，调用方阻塞等结果。"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._pw = None
            inst._browser = None
            inst._context = None
            inst._page = None
            inst._cmd_q = queue.Queue()
            inst._worker = threading.Thread(target=inst._worker_loop, daemon=True, name="browser-worker")
            inst._worker.start()
            cls._instance = inst
        return cls._instance

    def _worker_loop(self):
        # 唯一允许触碰 Playwright 对象的线程
        while True:
            item = self._cmd_q.get()
            if item is None:
                break
            fn, args, kw, out_q = item
            try:
                out_q.put(("ok", fn(*args, **kw)))
            except Exception as e:
                out_q.put(("err", e))

    def _run(self, fn, *args, **kw):
        # 把实际操作派发到 worker 线程并同步等待结果/异常
        out_q = queue.Queue()
        self._cmd_q.put((fn, args, kw, out_q))
        kind, val = out_q.get(timeout=120)
        if kind == "err":
            raise val
        return val

    # ===== 以下 _impl_* 全部在 worker 线程内执行 =====
    def _ensure(self):
        if self._page is not None:
            return self._page
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        self._context = self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        self._page = self._context.new_page()
        return self._page

    def _impl_open(self, url, wait_until, timeout):
        page = self._ensure()
        page.goto(url, wait_until=wait_until, timeout=timeout)
        return {"ok": True, "url": page.url, "title": page.title()}
    def open(self, url, wait_until="domcontentloaded", timeout=30000):
        return self._run(self._impl_open, url, wait_until, timeout)

    def _impl_click(self, selector, timeout):
        self._ensure().click(selector, timeout=timeout); return {"ok": True, "clicked": selector}
    def click(self, selector, timeout=10000):
        return self._run(self._impl_click, selector, timeout)

    def _impl_type(self, selector, text, timeout):
        self._ensure().fill(selector, text, timeout=timeout); return {"ok": True, "typed": text[:50], "selector": selector}
    def type(self, selector, text, timeout=10000):
        return self._run(self._impl_type, selector, text, timeout)

    def _impl_press(self, key):
        self._ensure().keyboard.press(key); return {"ok": True, "pressed": key}
    def press(self, key):
        return self._run(self._impl_press, key)

    def _impl_screenshot(self, path):
        if not path:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_" + str(int(time.time())) + ".png")
        self._ensure().screenshot(path=path, full_page=False)
        return {"ok": True, "path": path}
    def screenshot(self, path=None):
        return self._run(self._impl_screenshot, path)

    def _impl_get_text(self, selector):
        page = self._ensure()
        text = page.inner_text(selector)[:5000] if selector else page.inner_text("body")[:8000]
        return {"ok": True, "text": text}
    def get_text(self, selector=None):
        return self._run(self._impl_get_text, selector)

    def _impl_get_html(self, selector):
        page = self._ensure()
        html = page.inner_html(selector)[:10000] if selector else page.content()[:15000]
        return {"ok": True, "html": html}
    def get_html(self, selector=None):
        return self._run(self._impl_get_html, selector)

    def _impl_wait(self, selector, timeout):
        self._ensure().wait_for_selector(selector, timeout=timeout); return {"ok": True, "waited": selector}
    def wait(self, selector, timeout=15000):
        return self._run(self._impl_wait, selector, timeout)

    def _impl_scroll(self, direction, amount):
        page = self._ensure()
        page.mouse.wheel(0, amount if direction == "down" else -amount)
        return {"ok": True, "scrolled": direction, "amount": amount}
    def scroll(self, direction="down", amount=500):
        return self._run(self._impl_scroll, direction, amount)

    def _impl_evaluate(self, script):
        result = self._ensure().evaluate(script)
        return {"ok": True, "result": str(result)[:5000] if result is not None else None}
    def evaluate(self, script):
        return self._run(self._impl_evaluate, script)

    def _impl_back(self):
        page = self._ensure(); page.go_back(); return {"ok": True, "url": page.url}
    def back(self):
        return self._run(self._impl_back)

    def _impl_forward(self):
        page = self._ensure(); page.go_forward(); return {"ok": True, "url": page.url}
    def forward(self):
        return self._run(self._impl_forward)

    def _impl_reload(self):
        page = self._ensure(); page.reload(wait_until="domcontentloaded"); return {"ok": True, "url": page.url}
    def reload(self):
        return self._run(self._impl_reload)

    def _impl_close(self):
        # 关闭并释放全部资源（均在 worker 线程内完成，避免跨线程）
        try:
            if self._page: self._page.close()
        except Exception: pass
        try:
            if self._context: self._context.close()
        except Exception: pass
        try:
            if self._browser: self._browser.close()
        except Exception: pass
        try:
            if self._pw: self._pw.stop()
        except Exception: pass
        self._page = None; self._context = None; self._browser = None; self._pw = None
        return {"ok": True, "message": "浏览器已关闭"}
    def close(self):
        return self._run(self._impl_close)

    def _impl_download(self, url, save_path):
        self._ensure()
        if not save_path:
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_" + url.split("/")[-1][:50])
        response = self._context.request.get(url)
        body = response.body()  # 只读取一次
        with open(save_path, "wb") as f:
            f.write(body)
        return {"ok": True, "path": save_path, "size": len(body)}
    def download(self, url, save_path=None):
        return self._run(self._impl_download, url, save_path)

_browser = BrowserManager()


def do_tool(name, params):
    # ---- 只读：目录/文件 ----
    if name == "list_dir":
        path = params.get("path", ".")
        if not os.path.exists(path):
            return {"error": "路径不存在：" + path}
        try:
            items = []
            for e in os.scandir(path):
                try:
                    items.append({"name": e.name, "type": "dir" if e.is_dir() else "file",
                                  "size": e.stat().st_size if not e.is_dir() else 0})
                except Exception:
                    pass
            return {"path": path, "items": items[:300], "count": len(items)}
        except Exception as e:
            return {"error": str(e)}
    if name == "read_file":
        path = params.get("path", "")
        if not os.path.exists(path):
            return {"error": "文件不存在：" + path}
        size = os.path.getsize(path)
        if size > 500 * 1024:
            return {"error": "文件过大（超过 500KB），只读取开头部分", "partial": True}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"path": path, "content": f.read()[:100000], "chars": min(size, 100000)}
        except Exception as e:
            return {"error": str(e)}

    # ---- 文档读写 ----
    if name == "read_doc":
        path = params.get("path", "")
        if not path:
            return {"error": "缺少路径"}
        return read_doc(path, meta_only=bool(params.get("_metaOnly")))
    if name == "stat_data":
        return stat_data(params)
    if name == "create_doc":
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return {"error": "缺少路径"}
        if not content and not params.get("confirmed"):
            return {"error": "内容为空"}
        if params.get("confirmed"):
            content = "__confirmed__" + content
        return create_doc(path, content)
    if name == "create_excel":
        path = params.get("path", "")
        headers = params.get("headers") or []
        rows = params.get("rows") or []
        sheet_name = params.get("sheet_name") or "Sheet1"
        if not path:
            return {"error": "缺少路径"}
        if not isinstance(headers, list) or not isinstance(rows, list):
            return {"error": "headers 和 rows 必须是数组"}
        if not path.lower().endswith(".xlsx"):
            path = path + ".xlsx"
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = str(sheet_name)[:31]
            # 写入表头
            for c, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=c, value=str(h))
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="DDEEFF", end_color="DDEEFF", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
            # 写入数据
            for r_i, row in enumerate(rows, 2):
                if isinstance(row, (list, tuple)):
                    for c, v in enumerate(row, 1):
                        ws.cell(row=r_i, column=c, value=v)
                else:
                    ws.cell(row=r_i, column=1, value=row)
            # 自动列宽
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        max_len = max(max_len, len(str(cell.value or "")))
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max_len + 2, 40)
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            wb.save(path)
            return {"ok": True, "path": path, "rows": len(rows), "cols": len(headers), "sheet": sheet_name}
        except Exception as e:
            return {"error": "创建Excel失败：" + str(e)[:300]}

    # ---- 写文件（覆盖需确认） ----
    if name == "write_file":
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return {"error": "缺少路径"}
        # 低风险写操作（创建/覆盖本地文件）：不弹审批，靠前端"写入后自动回读验证"兜底
        existed = os.path.exists(path)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"ok": True, "path": path, "chars": len(content), "overwritten": existed}
        except Exception as e:
            return {"error": str(e)}

    # ---- 文件操作（均需确认） ----
    if name == "file_copy":
        src, dst = params.get("src", ""), params.get("dst", "")
        if not (src and dst):
            return {"error": "缺少 src/dst"}
        if not params.get("confirmed"):
            return _need("file_copy", f"复制文件：{src} → {dst}", {"src": src, "dst": dst})
        try:
            shutil.copy2(src, dst)
            return {"ok": True, "copied": src, "to": dst}
        except Exception as e:
            return {"error": str(e)}
    if name == "file_move":
        src, dst = params.get("src", ""), params.get("dst", "")
        if not (src and dst):
            return {"error": "缺少 src/dst"}
        if not params.get("confirmed"):
            return _need("file_move", f"移动/重命名文件：{src} → {dst}", {"src": src, "dst": dst})
        try:
            shutil.move(src, dst)
            return {"ok": True, "moved": src, "to": dst}
        except Exception as e:
            return {"error": str(e)}
    if name == "file_delete":
        path = params.get("path", "")
        if not path:
            return {"error": "缺少路径"}
        if not params.get("confirmed"):
            return _need("file_delete", "删除文件（不可恢复）：" + path, {"path": path})
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"ok": True, "deleted": path}
        except Exception as e:
            return {"error": str(e)}

    # ---- 命令 ----
    if name == "run_command":
        cmd = params.get("cmd", "") or params.get("command", "")
        if not cmd.strip():
            return {"error": "命令为空（参数名应为 cmd）"}
        # 强制 background=False，防止模型误传参数导致弹窗
        return run_command(cmd, confirmed=params.get("confirmed", False),
                           timeout=int(params.get("timeout", 30)),
                           background=False)

    # ---- 计算器 ----
    if name == "calculator":
        expr = params.get("expr", "").strip()
        if not expr:
            return {"error": "缺少表达式"}
        try:
            val = safe_calc(expr)
            return {"expr": expr, "result": val}
        except Exception as e:
            return {"error": "无法计算：" + str(e)}

    # ---- 剪贴板 ----
    if name == "clipboard_get":
        r = ps_run("Get-Clipboard -Raw -ErrorAction SilentlyContinue")
        return {"text": (r.stdout or "")[:100000]}
    if name == "clipboard_set":
        text = params.get("text", "")
        if not params.get("confirmed") and len(text) > 50:
            return _need("clipboard_set", f"将以下内容写入剪贴板（{len(text)} 字符）：\n{text[:120]}{'…' if len(text)>120 else ''}",
                         {"text": text})
        tmp = os.path.join(os.environ.get("TEMP", "D:\\llama"), "_clip_tmp.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        r = ps_run("Set-Clipboard -Value (Get-Content -Raw -Encoding UTF8 '" + tmp.replace("'", "''") + "')")
        return {"ok": r.returncode == 0, "chars": len(text)}

    # ---- 截屏 ----
    if name == "screenshot":
        out_dir = params.get("dir", "D:\\llama\\screenshots")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "shot_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
            "$bmp.Save('" + path.replace("'", "''") + "');"
        )
        r = ps_run(script, timeout=40)
        if r.returncode == 0 and os.path.exists(path):
            return {"ok": True, "path": path, "size": os.path.getsize(path)}
        return {"error": "截屏失败：" + (r.stderr or "")[:500]}

    # ---- 图片：OCR 识图（RapidOCR 本地引擎，离线） ----
    if name == "ocr_image":
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return {"error": "图片不存在：" + path}
        try:
            global _OCR_ENGINE
            if _OCR_ENGINE is None:
                from rapidocr_onnxruntime import RapidOCR
                _OCR_ENGINE = RapidOCR()
            result, elapse = _OCR_ENGINE(path)
            lines = []
            if result:
                for item in result:
                    text = str(item[1]).strip()
                    if text:
                        lines.append(text)
            text = "\n".join(lines)
            return {"ok": True, "path": path, "text": text, "chars": len(text), "lines": len(lines)}
        except ImportError:
            return {"error": "OCR 引擎未安装（rapidocr_onnxruntime）"}
        except Exception as e:
            return {"error": "OCR 失败：" + str(e)[:300]}

    # ---- 图片：信息（尺寸/格式/大小） ----
    if name == "image_info":
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return {"error": "文件不存在：" + path}
        size = os.path.getsize(path)
        if size > 50 * 1024 * 1024:
            return {"error": "文件过大"}
        p_arg = path.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Drawing;"
            "try { $i=[System.Drawing.Image]::FromFile('" + p_arg + "');"
            "Write-Output ('{0}x{1}|{2}' -f $i.Width,$i.Height,$i.RawFormat);"
            "$i.Dispose() } catch { Write-Output ('ERR:'+$_.Exception.Message) }"
        )
        r = ps_run(script, timeout=40)
        meta = (r.stdout or "").strip()
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        info = {"path": path, "bytes": size, "ext": ext or "unknown"}
        m = re.match(r"^(\d+)x(\d+)\|(.+)$", meta)
        if m:
            info["width"] = int(m.group(1)); info["height"] = int(m.group(2)); info["format"] = m.group(3)
        else:
            info["format"] = meta or "未知"
        return {"ok": True, "info": info}

    # ---- 系统信息 ----
    if name == "system_info":
        script = (
            "$os=Get-CimInstance Win32_OperatingSystem;"
            "$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1;"
            "$mem=Get-CimInstance Win32_ComputerSystem;"
            "$drives=Get-PSDrive -PSProvider FileSystem | ForEach-Object {if($_.Used -ne $null){'{0}  {1:N1}GB/{2:N1}GB' -f $_.Name,$_.Used/1GB,($_.Used+$_.Free)/1GB}};"
            "$gpu=Get-CimInstance Win32_VideoController | Select-Object -First 1;"
            "Write-Output ('OS: '+$os.Caption+' '+$os.Version);"
            "Write-Output ('CPU: '+$cpu.Name);"
            "Write-Output ('MEM: '+[math]::Round(($mem.TotalPhysicalMemory/1GB),1)+' GB');"
            "Write-Output ('GPU: '+$gpu.Name);"
            "Write-Output 'DRIVES:'; $drives;"
        )
        r = ps_run(script, timeout=40)
        # 常用路径
        user_home = os.path.expanduser("~")
        paths = {
            "home": user_home,
            "desktop": os.path.join(user_home, "Desktop"),
            "documents": os.path.join(user_home, "Documents"),
            "downloads": os.path.join(user_home, "Downloads"),
            "pictures": os.path.join(user_home, "Pictures"),
            "d_llama": r"D:\llama",
            "webui": r"D:\llama\webui",
            "uploads": r"D:\llama\uploads",
        }
        exist_paths = {k: {"path": v, "exists": os.path.isdir(v)} for k, v in paths.items()}
        return {"info": (r.stdout or "")[:3000], "stderr": (r.stderr or "")[:500], "paths": exist_paths}

    # ---- 股票实时行情 ----
    if name == "stock_quote":
        code = str(params.get("code", "")).strip().lower()
        if not code:
            return {"error": "缺少股票代码"}
        try:
            if re.match(r"^(sz|sh|bj)\d{6}$", code):
                market, num = code[:2], code[2:]
            elif re.match(r"^\d{6}$", code):
                num = code
                if num.startswith("6"): market = "sh"
                elif num.startswith(("0", "3")): market = "sz"
                elif num.startswith(("4", "8")): market = "bj"
                else: market = "sz"
            else:
                return {"error": "代码格式不正确，应为 6 位数字（可带 sz/sh/bj 前缀），如 000001 或 sh600519"}
            url = "http://qt.gtimg.cn/q=" + market + num
            raw = urllib.request.urlopen(url, timeout=12).read()
            text = raw.decode("gbk", errors="replace")
            if "none_match" in text or '=""' in text or '"="' in text:
                return {"error": "未找到代码 " + code + "：可能不是有效股票代码（请确认交易所前缀，深市 sz/沪市 sh/北交所 bj），或代码有误"}
            body = text.split('"')[1]
            f = body.split("~")
            if len(f) < 40:
                return {"error": "行情解析失败"}
            return {
                "ok": True, "code": f[2], "name": f[1], "price": f[3], "prev_close": f[4],
                "open": f[5], "volume_hand": f[6], "change": f[31], "change_pct": f[32],
                "high": f[33], "low": f[34], "turnover_rate": f[38], "pe": f[39],
                "amplitude": f[43], "circ_mv_yi": f[44], "total_mv_yi": f[45], "pb": f[46],
                "time": f[30]
            }
        except Exception as e:
            return {"error": "行情查询失败：" + str(e)[:200]}

    # ---- 基金信息（fund API 屏蔽沙箱出口，走 PowerShell 直连） ----
    if name == "fund_info":
        code = str(params.get("code", "")).strip()
        if not re.match(r"^\d{6}$", code):
            return {"error": "基金代码应为 6 位数字"}
        tmp = os.path.join(tempfile.gettempdir(), "rui_fund_%d.json" % int(time.time() * 1000))
        tmp_arg = tmp.replace("'", "''")
        ps = (
            "try { $j = Invoke-RestMethod -Uri 'https://fundmobapi.eastmoney.com/FundMNewApi/"
            "FundMNBasicInformation?FCODE=" + code + "&deviceid=Wap&plat=Wap&product=EFund&version=6.2.8' "
            "-TimeoutSec 12; $d = $j.Datas; "
            "if ($null -eq $d) { Write-Output '__NOFUND__'; exit 0 }; "
            "$o = [PSCustomObject]@{code=$d.FCODE; name=$d.SHORTNAME; type=$d.FTYPE; nav_date=$d.FSRQ; chg=$d.RZDF; nav=$d.DWJZ; cum=$d.LJJZ}; "
            "$o | ConvertTo-Json -Compress | Out-File -FilePath '" + tmp_arg + "' -Encoding utf8; "
            "Write-Output '__OK__' } catch { Write-Output ('__ERR__ ' + $_.Exception.Message) }"
        )
        r = ps_run(ps, timeout=40)
        out = (r.stdout or "").strip()
        if "__NOFUND__" in out or "__ERR__" in out:
            try: os.remove(tmp)
            except Exception: pass
            return {"error": "未找到基金 " + code if "__NOFUND__" in out else ("基金查询失败：" + out[:200])}
        if not os.path.exists(tmp):
            return {"error": "基金查询失败：" + (r.stderr or out or "无输出")[:200]}
        try:
            with open(tmp, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
        except Exception:
            d = {}
        finally:
            try: os.remove(tmp)
            except Exception: pass
        if not d.get("code"):
            return {"error": "未找到基金 " + code}
        return {"ok": True, "code": d.get("code"), "name": d.get("name"), "type": d.get("type"),
                "nav_date": d.get("nav_date") or "无", "daily_change_pct": d.get("chg"),
                "unit_nav": d.get("nav"), "cum_nav": d.get("cum")}

    # ---- 当前时间 ----
    if name == "get_time":
        now = datetime.now()
        try:
            wd = "一二三四五六日"[now.weekday()]
            return {"ok": True, "datetime": now.strftime("%Y-%m-%d %H:%M:%S"), "weekday": "星期" + wd, "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S")}
        except Exception:
            return {"ok": True, "datetime": now.strftime("%Y-%m-%d %H:%M:%S")}

    # ---- 联网 ----
    if name == "web_search":
        q = params.get("query", "")
        if not q:
            return {"error": "缺少 query"}
        try:
            _res = search(q, int(params.get("n", 5)))
        except Exception as _e:
            return {"ok": False, "results": [], "error": "搜索异常：" + str(_e)[:200]}
        if not _res:
            # 明确返回失败，前端据此提示并让模型换词重试，而不是把空结果当成功诱导编造
            return {"ok": False, "results": [], "error": "所有搜索源均未返回结果（可能网络受限），请更换关键词重试"}
        return {"ok": True, "results": _res}
    if name == "fetch_url":
        url = params.get("url", "")
        if not url.startswith(("http://", "https://")):
            return {"error": "非法 URL"}
        return fetch_text(url)

    # ---- 飞书工具 ----
    if name.startswith("feishu_"):
        token = feishu_get_token()
        if not token:
            return {"error": "飞书未配置：请在 agent_server.py 顶部设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET（或环境变量）"}
        # 飞书文档读取（不需要 app_token）
        if name == "feishu_read_doc":
            doc_id = params.get("document_id", "") or params.get("doc_id", "")
            if not doc_id:
                return {"error": "缺少 document_id（飞书文档链接中 /docx/ 后面的字符串）"}
            try:
                r = feishu_api("GET", "/docx/v1/documents/" + doc_id + "/raw_content", token)
                if r.get("code") == 0:
                    content = r.get("data", {}).get("content", "")
                    return {"ok": True, "document_id": doc_id, "content": content[:20000], "chars": len(content)}
                return {"error": r.get("msg", "读取文档失败"), "code": r.get("code")}
            except Exception as e:
                return {"error": "读取文档异常：" + str(e)}
        app_token = params.get("app_token", "")
        table_id = params.get("table_id", "")
        if not app_token:
            return {"error": "缺少 app_token（多维表格链接中 /base/ 后面的字符串）"}
        if name == "feishu_list_tables":
            r = feishu_api("GET", "/bitable/v1/apps/" + app_token + "/tables", token)
            if r.get("code") == 0:
                items = [{"table_id": t.get("table_id"), "name": t.get("name")} for t in r.get("data", {}).get("items", [])]
                return {"ok": True, "tables": items, "count": len(items)}
            return {"error": r.get("msg", "获取数据表失败"), "code": r.get("code")}
        if not table_id:
            return {"error": "缺少 table_id（可先用 feishu_list_tables 获取）"}
        if name == "feishu_read_records":
            page_size = min(int(params.get("page_size", 20)), 100)
            page_token = params.get("page_token", "")
            path = "/bitable/v1/apps/" + app_token + "/tables/" + table_id + "/records?page_size=" + str(page_size)
            if page_token:
                path += "&page_token=" + urllib.parse.quote(page_token)
            r = feishu_api("GET", path, token)
            if r.get("code") == 0:
                records = [{"record_id": rec.get("record_id"), "fields": rec.get("fields", {})} for rec in r.get("data", {}).get("items", [])]
                return {"ok": True, "records": records, "count": len(records),
                        "has_more": r.get("data", {}).get("has_more", False),
                        "page_token": r.get("data", {}).get("page_token", "")}
            return {"error": r.get("msg", "读取记录失败"), "code": r.get("code")}
        if name == "feishu_search_records":
            filter_expr = params.get("filter", "")
            page_size = min(int(params.get("page_size", 20)), 100)
            body = {"page_size": page_size}
            if filter_expr:
                body["filter"] = {"conjunction": "and", "conditions": [{"field_name": f.split("=")[0].strip(), "operator": "is", "value": [f.split("=", 1)[1].strip()]} for f in filter_expr.split(";") if "=" in f]}
            r = feishu_api("POST", "/bitable/v1/apps/" + app_token + "/tables/" + table_id + "/records/search", token, body)
            if r.get("code") == 0:
                records = [{"record_id": rec.get("record_id"), "fields": rec.get("fields", {})} for rec in r.get("data", {}).get("items", [])]
                return {"ok": True, "records": records, "count": len(records),
                        "has_more": r.get("data", {}).get("has_more", False),
                        "page_token": r.get("data", {}).get("page_token", "")}
            return {"error": r.get("msg", "搜索记录失败"), "code": r.get("code")}
        if name == "feishu_create_record":
            fields = params.get("fields", {})
            if not fields:
                return {"error": "缺少 fields（字段名: 值 的字典）"}
            if not params.get("confirmed"):
                return _need("feishu_create_record", "将向飞书多维表格新增一条记录：" + json.dumps(fields, ensure_ascii=False)[:200], params)
            r = feishu_api("POST", "/bitable/v1/apps/" + app_token + "/tables/" + table_id + "/records", token, {"fields": fields})
            if r.get("code") == 0:
                return {"ok": True, "record_id": r.get("data", {}).get("record", {}).get("record_id"), "fields": r.get("data", {}).get("record", {}).get("fields", {})}
            return {"error": r.get("msg", "新增记录失败"), "code": r.get("code")}
        if name == "feishu_update_record":
            record_id = params.get("record_id", "")
            fields = params.get("fields", {})
            if not record_id:
                return {"error": "缺少 record_id"}
            if not fields:
                return {"error": "缺少 fields"}
            if not params.get("confirmed"):
                return _need("feishu_update_record", "将更新飞书记录 " + record_id + "：" + json.dumps(fields, ensure_ascii=False)[:200], params)
            r = feishu_api("PUT", "/bitable/v1/apps/" + app_token + "/tables/" + table_id + "/records/" + record_id, token, {"fields": fields})
            if r.get("code") == 0:
                return {"ok": True, "record_id": record_id, "fields": r.get("data", {}).get("record", {}).get("fields", {})}
            return {"error": r.get("msg", "更新记录失败"), "code": r.get("code")}
        return {"error": "未知飞书工具：" + name}

    # ---- 浏览器自动化 ----
    if name == "browser_open":
        url = params.get("url", "")
        if not url:
            return {"error": "缺少 url"}
        if not url.startswith("http"):
            url = "https://" + url
        try:
            return _browser.open(url, wait_until=params.get("wait_until", "domcontentloaded"))
        except Exception as e:
            return {"error": "打开页面失败：" + str(e)[:200]}
    if name == "browser_click":
        selector = params.get("selector", "")
        if not selector:
            return {"error": "缺少 selector（CSS选择器）"}
        try:
            return _browser.click(selector)
        except Exception as e:
            return {"error": "点击失败：" + str(e)[:200]}
    if name == "browser_type":
        selector = params.get("selector", "")
        text = params.get("text", "")
        if not selector or not text:
            return {"error": "缺少 selector 或 text"}
        try:
            return _browser.type(selector, text)
        except Exception as e:
            return {"error": "输入失败：" + str(e)[:200]}
    if name == "browser_press":
        key = params.get("key", "Enter")
        try:
            return _browser.press(key)
        except Exception as e:
            return {"error": "按键失败：" + str(e)[:200]}
    if name == "browser_screenshot":
        try:
            return _browser.screenshot(params.get("path"))
        except Exception as e:
            return {"error": "截图失败：" + str(e)[:200]}
    if name == "browser_get_text":
        try:
            return _browser.get_text(params.get("selector"))
        except Exception as e:
            return {"error": "获取文本失败：" + str(e)[:200]}
    if name == "browser_get_html":
        try:
            return _browser.get_html(params.get("selector"))
        except Exception as e:
            return {"error": "获取HTML失败：" + str(e)[:200]}
    if name == "browser_wait":
        selector = params.get("selector", "")
        if not selector:
            return {"error": "缺少 selector"}
        try:
            return _browser.wait(selector, timeout=int(params.get("timeout", 15000)))
        except Exception as e:
            return {"error": "等待失败：" + str(e)[:200]}
    if name == "browser_scroll":
        try:
            return _browser.scroll(direction=params.get("direction", "down"), amount=int(params.get("amount", 500)))
        except Exception as e:
            return {"error": "滚动失败：" + str(e)[:200]}
    if name == "browser_evaluate":
        script = params.get("script", "")
        if not script:
            return {"error": "缺少 script（JavaScript代码）"}
        try:
            return _browser.evaluate(script)
        except Exception as e:
            return {"error": "执行JS失败：" + str(e)[:200]}
    if name == "browser_back":
        try:
            return _browser.back()
        except Exception as e:
            return {"error": "后退失败：" + str(e)[:200]}
    if name == "browser_forward":
        try:
            return _browser.forward()
        except Exception as e:
            return {"error": "前进失败：" + str(e)[:200]}
    if name == "browser_reload":
        try:
            return _browser.reload()
        except Exception as e:
            return {"error": "刷新失败：" + str(e)[:200]}
    if name == "browser_close":
        try:
            return _browser.close()
        except Exception as e:
            return {"error": "关闭失败：" + str(e)[:200]}
    if name == "browser_download":
        url = params.get("url", "")
        if not url:
            return {"error": "缺少 url"}
        try:
            return _browser.download(url, params.get("save_path"))
        except Exception as e:
            return {"error": "下载失败：" + str(e)[:200]}

    return {"error": "未知工具：" + name}

# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def _cors_origin(self):
        """CORS来源白名单：仅允许本地 + 局域网，反射回请求Origin（替代*）"""
        origin = self.headers.get("Origin", "")
        for prefix in ["http://127.0.0.1", "http://localhost", "http://192.168.", "http://10."]:
            if origin.startswith(prefix):
                return origin
        return "http://127.0.0.1:8080"

    def _check_token(self):
        """访问Token检查：启用了则要求 X-Access-Token 头，未启用不强制"""
        if not ACCESS_TOKEN:
            return True
        return self.headers.get("X-Access-Token", "") == ACCESS_TOKEN

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Access-Token")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, download=False):
        data = open(path, "rb").read()
        name = os.path.basename(path)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Content-Length", str(len(data)))
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="' + urllib.parse.quote(name) + '"')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Access-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/health":
                return self._send(200, {"ok": True, "service": "agent", "port": PORT})
            if not self._check_token():
                return self._send(401, {"error": "未授权：缺少或错误的访问Token（X-Access-Token）"})
            qs = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/search":
                q = (qs.get("q") or [""])[0].strip()
                n = int((qs.get("n") or ["5"])[0])
                if not q:
                    return self._send(400, {"error": "缺少参数 q"})
                return self._send(200, {"query": q, "results": search(q, max(1, min(n, 10)))})
            if parsed.path == "/api/fetch":
                url = (qs.get("url") or [""])[0].strip()
                if not url.startswith(("http://", "https://")):
                    return self._send(400, {"error": "非法 URL"})
                return self._send(200, fetch_text(url))
            if parsed.path == "/api/download":
                p = (qs.get("path") or [""])[0].strip()
                if not p or not os.path.isfile(p):
                    return self._send(404, {"error": "文件不存在"})
                if not _is_path_allowed(p):
                    return self._send(403, {"error": "路径不在允许访问的目录内（安全策略）"})
                return self._send_file(p, download=True)
            if parsed.path == "/api/open":
                p = (qs.get("path") or [""])[0].strip()
                if not p or not os.path.exists(p):
                    return self._send(404, {"error": "路径不存在"})
                if not _is_path_allowed(p):
                    return self._send(403, {"error": "路径不在允许访问的目录内（安全策略）"})
                try:
                    os.startfile(p)
                    return self._send(200, {"ok": True, "path": p})
                except Exception as e:
                    return self._send(500, {"error": str(e)})
            if parsed.path == "/api/raw":
                p = (qs.get("path") or [""])[0].strip()
                if not p or not os.path.isfile(p):
                    return self._send(404, {"error": "文件不存在"})
                if not _is_path_allowed(p):
                    return self._send(403, {"error": "路径不在允许访问的目录内（安全策略）"})
                ext = os.path.splitext(p)[1].lower()
                ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}.get(ext, "application/octet-stream")
                data = open(p, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", self._cors_origin())
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/api/models":
                return self._send(200, list_models())
            if parsed.path == "/api/rui/state":
                key = (qs.get("key") or [""])[0].strip()
                if not key or not _VALID_KEY.match(key):
                    return self._send(400, {"error": "非法 key"})
                p = os.path.join(RUI_STATE_DIR, key + ".json")
                if not os.path.isfile(p):
                    return self._send(200, {"key": key, "value": None})
                with open(p, "r", encoding="utf-8") as f:
                    return self._send(200, {"key": key, "value": json.load(f)})
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if not self._check_token():
            return self._send(401, {"error": "未授权：缺少或错误的访问Token（X-Access-Token）"})
        try:
            if parsed.path == "/api/rui/state":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                key = str(body.get("key", "")).strip()
                if not key or not _VALID_KEY.match(key):
                    return self._send(400, {"error": "非法 key"})
                os.makedirs(RUI_STATE_DIR, exist_ok=True)
                with open(os.path.join(RUI_STATE_DIR, key + ".json"), "w", encoding="utf-8") as f:
                    json.dump(body.get("value"), f, ensure_ascii=False)
                return self._send(200, {"ok": True, "key": key})
            if parsed.path == "/api/switch_model":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                model_key = str(body.get("model", "")).strip()
                result = switch_model(model_key)
                return self._send(200, result)
            if parsed.path == "/api/upload":
                length = int(self.headers.get("Content-Length", 0))
                name = urllib.parse.parse_qs(parsed.query).get("name", ["upload.png"])[0]
                name = os.path.basename(name)[:80]
                up_dir = "D:\\llama\\uploads"
                os.makedirs(up_dir, exist_ok=True)
                path = os.path.join(up_dir, name)
                if os.path.exists(path):
                    stem, ext = os.path.splitext(name)
                    path = os.path.join(up_dir, stem + "_" + str(int(time.time() * 1000)) + ext)
                data = self.rfile.read(length) if length else b""
                if not data:
                    return self._send(400, {"error": "空文件"})
                with open(path, "wb") as f:
                    f.write(data)
                return self._send(200, {"ok": True, "path": path, "bytes": len(data)})
            if parsed.path != "/api/exec":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            tool = body.get("tool", "")
            params = body.get("params", {}) or {}
            result = do_tool(tool, params)
            return self._send(200, result)
        except Exception as e:
            return self._send(500, {"error": str(e)})


def main():
    restart_count = 0
    while True:
        try:
            srv = ThreadingHTTPServer((HOST, PORT), Handler)
            srv.daemon_threads = True
            print(f"[agent_server] 已启动: http://{HOST}:{PORT} (多线程模式, 重启次数:{restart_count})", flush=True)
            srv.serve_forever()
        except Exception as e:
            restart_count += 1
            print(f"[agent_server] 崩溃! 错误: {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            print(f"[agent_server] 3秒后自动重启 (第{restart_count}次)...", flush=True)
            time.sleep(3)
            try:
                srv.server_close()
            except:
                pass


if __name__ == "__main__":
    main()
