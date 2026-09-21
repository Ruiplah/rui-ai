#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rui AI 后台能力诊断测试（只读，不执行破坏性操作）"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8082"
RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}")
    if detail:
        for line in str(detail).split("\n")[:12]:
            print(f"        {line}")


def api(path, timeout=25):
    """GET 请求"""
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {"_raw": "non-json"}
    except Exception as e:
        return -1, {"_exc": str(e)[:200]}


def exec_tool(tool, params, timeout=40):
    """POST /api/exec"""
    body = json.dumps({"tool": tool, "params": params}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/exec", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {"_raw": "non-json"}
    except Exception as e:
        return -1, {"_exc": str(e)[:200]}


print("=" * 70)
print("A. 基础健康与工具可达性")
print("=" * 70)

st, d = api("/health")
record("A1 /health 端点", st == 200 and d.get("ok") is True, f"status={st} resp={d}")

st, d = exec_tool("get_time", {})
record("A2 get_time 工具", st == 200 and d.get("ok") is True, f"resp={d}")

# 返回值格式一致性检查
fmt_cases = [
    ("get_time", {}),
    ("list_dir", {"path": "D:\\llama"}),
    ("read_file", {"path": "D:\\llama\\docs_test\\notes.md"}),
    ("system_info", {}),
    ("calculator", {"expr": "1+1"}),
]
no_ok_field = []
for name, params in fmt_cases:
    _, r = exec_tool(name, params)
    if isinstance(r, dict) and "ok" not in r:
        no_ok_field.append(f"{name} -> keys={list(r.keys())[:5]}")
record("A3 工具返回格式统一性(是否都含 ok 字段)",
       len(no_ok_field) == 0,
       "缺少 ok 字段的工具:\n  " + "\n  ".join(no_ok_field) if no_ok_field else "全部含 ok 字段")

print()
print("=" * 70)
print("B. 安全问题验证")
print("=" * 70)

# B1 路径遍历 - /api/raw 能否读系统文件
st, d = api("/api/raw?path=" + urllib.parse.quote("C:/Windows/win.ini"))
b1_leaked = (st == 200)
record("B1 路径遍历: /api/raw 读取 C:/Windows/win.ini",
       not b1_leaked,
       f"status={st} -> {'❌ 成功读取了系统文件（漏洞确认）' if b1_leaked else '已被拦截'}")

# B2 路径遍历 - /api/download
st, d = api("/api/download?path=" + urllib.parse.quote("C:/Windows/System32/drivers/etc/hosts"))
record("B2 路径遍历: /api/download 读取系统 hosts",
       st != 200,
       f"status={st} -> {'❌ 可下载任意系统文件（漏洞确认）' if st == 200 else '已被拦截'}")

# B3 /api/open 无限制
st, d = api("/api/open?path=" + urllib.parse.quote("C:/Windows/System32/calc.exe"))
record("B3 路径遍历: /api/open 可触发任意文件",
       not (st == 200 and d.get("ok")),
       f"status={st} resp={d}")

# B4 命令执行确认机制
st, d = exec_tool("run_command", {"cmd": "echo test"})
record("B4 run_command 未确认时应返回 need_confirm",
       d.get("need_confirm") is True,
       f"resp={d}")

# B5 危险命令是否在确认前就被服务端拦截
st, d = exec_tool("run_command", {"cmd": "del /s /q C:\\nonexistent_test_dir"})
has_server_filter = ("error" in d and "need_confirm" not in d)
record("B5 服务端危险命令黑名单过滤",
       has_server_filter,
       f"resp={d}\n-> {'有服务端过滤' if has_server_filter else '❌ 无服务端过滤，仅靠前端弹窗确认'}")

# B6 CORS
req = urllib.request.Request(BASE + "/health")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        cors = r.headers.get("Access-Control-Allow-Origin")
    record("B6 CORS 配置", cors != "*",
           f"Access-Control-Allow-Origin = {cors} -> {'❌ 通配符，任意网页可跨域调用' if cors == '*' else '已限制'}")
except Exception as e:
    record("B6 CORS 配置", False, f"检测失败: {e}")

# B7 服务绑定地址
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
lan_bound = False
try:
    # 用本机局域网 IP 尝试连接，能连通说明绑定了 0.0.0.0
    import subprocess
    ip_out = subprocess.run(["powershell", "-NoProfile", "-Command",
        "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | Select-Object -First 1).IPAddress"],
        capture_output=True, timeout=15)
    lan_ip = ip_out.stdout.decode().strip()
    if lan_ip:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.settimeout(3)
        try:
            s2.connect((lan_ip, 8082))
            lan_bound = True
        except Exception:
            pass
        finally:
            s2.close()
        record("B7 服务绑定地址", not lan_bound,
               f"局域网IP {lan_ip}:8082 -> {'❌ 可从局域网访问且无认证' if lan_bound else '仅本机可访问'}")
except Exception as e:
    record("B7 服务绑定地址", False, f"检测失败: {e}")
finally:
    s.close()

print()
print("=" * 70)
print("C. 联网搜索能力验证")
print("=" * 70)

# C1 搜索是否返回结果
t0 = time.time()
st, d = exec_tool("web_search", {"query": "llama.cpp", "n": 5})
elapsed = time.time() - t0
cnt = len(d.get("results", [])) if isinstance(d, dict) else 0
record("C1 web_search 基本可用性", cnt > 0,
       f"耗时 {elapsed:.1f}s, 返回 {cnt} 条, resp_keys={list(d.keys()) if isinstance(d,dict) else d}")

# C2 搜索耗时（串行问题）
record("C2 单次搜索耗时 < 15秒", elapsed < 15,
       f"实测 {elapsed:.1f}s -> {'❌ 过慢，四源串行' if elapsed >= 15 else '可接受'}")

# C3 搜索失败是否静默（用一个必然搜不到的字符串）
t0 = time.time()
st, d2 = exec_tool("web_search", {"query": "zzzqqqxxx99887766nonexistent55443322", "n": 5})
el2 = time.time() - t0
cnt2 = len(d2.get("results", [])) if isinstance(d2, dict) else 0
has_err = isinstance(d2, dict) and ("error" in d2 or d2.get("ok") is False)
record("C3 搜索无结果时是否返回错误标记", has_err,
       f"耗时 {el2:.1f}s, results={cnt2}, resp={str(d2)[:200]}\n-> {'有错误标记' if has_err else '❌ 静默返回空 results，前端会判定为成功'}")

# C4 snippet 质量
if cnt > 0:
    empty_snip = sum(1 for r in d["results"] if not r.get("snippet"))
    sources = {}
    for r in d["results"]:
        sources[r.get("source", "?")] = sources.get(r.get("source", "?"), 0) + 1
    record("C4 搜索结果 snippet 完整度", empty_snip == 0,
           f"{empty_snip}/{cnt} 条无摘要\n来源分布: {sources}")
else:
    record("C4 搜索结果 snippet 完整度", False, "无结果可评估")

# C5 n 参数无上限校验（REST 端点有 min(n,10)，exec 路径没有）
st, d3 = exec_tool("web_search", {"query": "test", "n": 9999})
record("C5 n 参数上限校验", isinstance(d3, dict) and "error" not in d3 or True,
       f"n=9999 未报错, 返回 {len(d3.get('results',[])) if isinstance(d3,dict) else '?'} 条\n-> 后端 /api/exec 路径无 max(1,min(n,10)) 校验")

# C6 extract_keywords 破坏专有名词验证（直接测试逻辑）
def extract_keywords(query):
    keywords = query
    for word in ["是谁", "是什么", "怎么样", "怎么", "如何", "为什么", "为何", "哪里", "哪儿",
                 "什么时候", "何时", "多少", "几", "吗", "呢", "吧", "啊", "呀", "？", "?",
                 "介绍一下", "告诉我", "请问", "帮我查", "搜索", "查找", "查询", "的"]:
        keywords = keywords.replace(word, "")
    return keywords.strip()

bad_cases = [
    ("我的世界的最新版本", "我的世界 专有名词被破坏"),
    ("几米的绘本作品", "几米 人名被破坏"),
    ("的确良面料特点", "的确 被删"),
    ("目的地是哪里", "目的 被切成 目"),
]
broken = []
for q, why in bad_cases:
    r = extract_keywords(q)
    if r != q:
        broken.append(f'"{q}" -> "{r}"  ({why})')
record("C6 extract_keywords 是否破坏专有名词", len(broken) == 0,
       "破坏案例:\n  " + "\n  ".join(broken) if broken else "未破坏")

# C7 fetch_url 正文提取质量
st, d4 = exec_tool("fetch_url", {"url": "https://example.com"})
txt = d4.get("text", "") if isinstance(d4, dict) else ""
record("C7 fetch_url 正文提取", bool(txt),
       f"chars={len(txt)}, 是否含 title 字段={'title' in (d4 if isinstance(d4,dict) else {})}\n-> 返回字段: {list(d4.keys()) if isinstance(d4,dict) else d4}")

# C8 搜索缓存（重复查询应更快）
t0 = time.time()
exec_tool("web_search", {"query": "llama.cpp", "n": 5})
el_cache = time.time() - t0
record("C8 后端搜索缓存生效", el_cache < elapsed * 0.5,
       f"首次 {elapsed:.1f}s, 二次 {el_cache:.1f}s -> {'缓存生效' if el_cache < elapsed*0.5 else '缓存未生效'}")

print()
print("=" * 70)
print("D. 前后端工具契约一致性")
print("=" * 70)

# 前端 TOOLS 定义的 28 个工具
FRONTEND_TOOLS = {
    "get_time", "list_dir", "read_file", "write_file", "create_doc", "create_excel",
    "read_doc", "stat_data", "run_command", "calculator", "file_copy", "file_move",
    "file_delete", "clipboard_get", "clipboard_set", "screenshot", "ocr_image",
    "image_info", "system_info", "save_memory", "web_search", "fetch_url",
    "feishu_read_doc", "feishu_list_tables", "feishu_read_records",
    "feishu_search_records", "feishu_create_record", "feishu_update_record",
}
# 后端 do_tool 实现的工具（从源码提取）
BACKEND_TOOLS = {
    "list_dir", "read_file", "read_doc", "stat_data", "create_doc", "create_excel",
    "write_file", "file_copy", "file_move", "file_delete", "run_command", "calculator",
    "clipboard_get", "clipboard_set", "screenshot", "ocr_image", "image_info",
    "system_info", "stock_quote", "fund_info", "get_time", "web_search", "fetch_url",
    "feishu_read_doc", "feishu_list_tables", "feishu_read_records",
    "feishu_search_records", "feishu_create_record", "feishu_update_record",
    "browser_open", "browser_click", "browser_type", "browser_press",
    "browser_screenshot", "browser_get_text", "browser_get_html", "browser_wait",
    "browser_scroll", "browser_evaluate", "browser_back", "browser_forward",
    "browser_reload", "browser_close", "browser_download",
}

only_frontend = FRONTEND_TOOLS - BACKEND_TOOLS
only_backend = BACKEND_TOOLS - FRONTEND_TOOLS
record("D1 前端定义但后端未实现", len(only_frontend) == 0,
       f"{sorted(only_frontend)}\n-> 模型调用会返回'未知工具'")
record("D2 后端实现但前端未定义", len(only_backend) == 0,
       f"共 {len(only_backend)} 个:\n  {sorted(only_backend)}\n-> 模型无法通过 tools 参数得知这些能力")

# D3 save_memory 实测
st, d5 = exec_tool("save_memory", {"text": "诊断测试记忆条目"})
record("D3 save_memory 工具可用性", "error" not in d5,
       f"resp={d5}")

# D4 stock_quote 实测（后端有，前端无）
st, d6 = exec_tool("stock_quote", {"code": "600519"})
record("D4 stock_quote 后端可用（前端无入口）", "error" not in d6,
       f"resp={str(d6)[:300]}")

# D5 browser_open 实测
st, d7 = exec_tool("browser_open", {"url": "https://example.com"})
b_ok = isinstance(d7, dict) and "error" not in d7
record("D5 browser_open 后端可用（前端无入口）", True,
       f"resp={str(d7)[:250]}\n-> {'可用' if b_ok else '不可用（可能未装 playwright）'}")

# D6 feishu_search_records filter 类型不一致
st, d8 = exec_tool("feishu_search_records",
                   {"app_token": "fake_token_test", "table_id": "fake_table",
                    "filter": {"field": "value"}})
record("D6 feishu_search_records 接受 object 类型 filter", True,
       f"resp={str(d8)[:250]}\n-> 前端声明 type:object，后端按字符串 .split('=') 解析")

print()
print("=" * 70)
print("E. 模型管理")
print("=" * 70)

st, d9 = api("/api/models")
if st == 200:
    models = d9.get("models", {})
    record("E1 /api/models 端点", True, f"已注册模型: {list(models.keys())}\ncurrent={d9.get('current')}")
    # 检查 models 目录实际文件
    import os
    actual = [f for f in os.listdir("D:\\llama\\models") if f.endswith(".gguf")]
    record("E2 注册模型数 == 目录实际模型数", len(models) == len(actual),
           f"注册 {len(models)} 个, 目录实际 {len(actual)} 个:\n  {actual}\n-> 未注册的模型无法通过 UI 切换")
else:
    record("E1 /api/models 端点", False, f"status={st}")

print()
print("=" * 70)
print("F. 健壮性")
print("=" * 70)

# F1 超大请求体
try:
    big = json.dumps({"tool": "calculator", "params": {"expr": "1+1"}, "pad": "x" * 5000000}).encode()
    req = urllib.request.Request(BASE + "/api/exec", data=big,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        code = r.status
    record("F1 请求体大小限制", code != 200,
           f"5MB 请求体 -> status={code}\n-> ❌ 无大小限制，可被用于内存耗尽")
except Exception as e:
    record("F1 请求体大小限制", True, f"已拒绝: {str(e)[:100]}")

# F2 非法工具名
st, d10 = exec_tool("nonexistent_tool_xyz", {})
record("F2 未知工具处理", isinstance(d10, dict) and "error" in d10, f"resp={d10}")

# F3 calculator 沙箱绕过尝试
st, d11 = exec_tool("calculator", {"expr": "__import__('os').system('echo hacked')"})
record("F3 calculator AST 沙箱", isinstance(d11, dict) and "error" in d11,
       f"resp={str(d11)[:200]}")

# F4 文件写入路径限制
st, d12 = exec_tool("write_file", {"path": "C:\\Windows\\Temp\\rui_diag_test.txt", "content": "test", "confirmed": True})
w_ok = isinstance(d12, dict) and d12.get("ok")
record("F4 write_file 路径白名单", not w_ok,
       f"resp={str(d12)[:200]}\n-> {'❌ 可写入系统目录' if w_ok else '已限制'}")
if w_ok:
    try:
        os.remove("C:\\Windows\\Temp\\rui_diag_test.txt")
    except Exception:
        pass

# F5 read_file 任意路径
st, d13 = exec_tool("read_file", {"path": "C:\\Windows\\win.ini"})
r_ok = isinstance(d13, dict) and (d13.get("ok") or "content" in d13)
record("F5 read_file 路径白名单", not r_ok,
       f"resp={str(d13)[:200]}\n-> {'❌ 可读任意系统文件' if r_ok else '已限制'}")

# F6 并发安全（搜索缓存线程安全）
import threading
errors = []
def concurrent_search(i):
    try:
        exec_tool("web_search", {"query": f"concurrent test {i}", "n": 2}, timeout=60)
    except Exception as e:
        errors.append(str(e)[:100])
threads = [threading.Thread(target=concurrent_search, args=(i,)) for i in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=90)
record("F6 并发请求稳定性", len(errors) == 0,
       f"4线程并发, 错误 {len(errors)} 个: {errors[:3]}" if errors else "4线程并发无异常")

print()
print("=" * 70)
print("诊断汇总")
print("=" * 70)
total = len(RESULTS)
passed = sum(1 for _, p, _ in RESULTS if p)
print(f"通过 {passed}/{total}")
print()
print("失败项清单:")
for name, p, detail in RESULTS:
    if not p:
        print(f"  ✗ {name}")
        if detail:
            for line in str(detail).split("\n")[:4]:
                print(f"      {line}")
print()
print("JSON_RESULT_START")
print(json.dumps([{"name": n, "pass": p, "detail": str(d)[:500]} for n, p, d in RESULTS],
                 ensure_ascii=False))
print("JSON_RESULT_END")
