# -*- coding: utf-8 -*-
import json, urllib.request

def post(tool, params):
    d = json.dumps({"tool": tool, "params": params}).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d,
        headers={"Content-Type": "application/json"}), timeout=60)
    return json.loads(r.read().decode("utf-8"))

print("== 计算器 ==", post("calculator", {"expr": "(15+3)*2^4 + sqrt(144)"}))
print("== 写文件(新建) ==", post("write_file", {"path": "D:\\llama\\test_agent\\hello.txt", "content": "你好，这是 Rui AI 写下的文件。"}))
print("== 写文件(覆盖,未确认应拦截) ==", post("write_file", {"path": "D:\\llama\\test_agent\\hello.txt", "content": "覆盖内容"}))
print("== 写文件(覆盖,已确认) ==", post("write_file", {"path": "D:\\llama\\test_agent\\hello.txt", "content": "覆盖内容", "confirmed": True}))
print("== 剪贴板写入 ==", post("clipboard_set", {"text": "Rui AI 剪贴板测试"}))
print("== 剪贴板读取 ==", post("clipboard_get", {}))
print("== 系统信息 ==")
si = post("system_info", {})
print(si.get("info", si)[:300])
print("== 文件删除(未确认应拦截) ==", post("file_delete", {"path": "D:\\llama\\test_agent\\hello.txt"}))
print("== 截屏 ==", post("screenshot", {"dir": "D:\\llama\\screenshots"}))
