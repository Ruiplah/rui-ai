# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse

def post(url, obj):
    d = json.dumps(obj).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request(url, data=d, headers={"Content-Type": "application/json"}), timeout=60)
    return json.loads(r.read().decode("utf-8"))

def get(url):
    r = urllib.request.urlopen(url, timeout=60)
    return json.loads(r.read().decode("utf-8"))

print("== 1. 安全命令 ==")
print(post("http://127.0.0.1:8082/api/exec", {"tool": "run_command", "params": {"command": "echo hello-agent"}}))
print("== 2. 安全命令(列目录) ==")
print(post("http://127.0.0.1:8082/api/exec", {"tool": "run_command", "params": {"command": 'cmd /c dir /b "D:\\llama"'}})[:200] if False else post("http://127.0.0.1:8082/api/exec", {"tool": "run_command", "params": {"command": 'dir /b D:\\llama'}}))
print("== 3. 危险命令(未确认) ==")
print(post("http://127.0.0.1:8082/api/exec", {"tool": "run_command", "params": {"command": "shutdown /s"}}))
print("== 4. 危险命令(确认后执行-用无害命令) ==")
print(post("http://127.0.0.1:8082/api/exec", {"tool": "run_command", "params": {"command": "shutdown /?"}}))
print("== 5. 搜索 ==")
res = get("http://127.0.0.1:8082/api/search?q=" + urllib.parse.quote("今天广州天气") + "&n=3")
for i, r in enumerate(res.get("results", [])):
    print(f"  {i+1}. {r['title'][:40]} | {r['url'][:60]}")
print("== 6. llama-server 健康(可能仍在加载) ==")
try:
    h = get("http://127.0.0.1:8080/health")
    print(h)
except Exception as e:
    print("模型仍在加载或未就绪:", e)
