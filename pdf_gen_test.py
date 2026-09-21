# -*- coding: utf-8 -*-
"""PDF 生成测试"""
import urllib.request, json, os, time, urllib.error

TOOLS = [{"type": "function", "function": {"name": "create_doc", "description": "创建 Word(.docx)、Excel(.xlsx)、PDF 或文本文档。pdf 建议用英文内容。扩展名决定格式。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}}]
SYS = ("你是 Rui AI。用 create_doc 创建文档；创建后告诉用户保存路径。")
msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": "创建一个 PDF 文件，内容是：Rui AI Project Report，保存到 D:\\llama\\test_output\\report.pdf"}]
body = {"model": "qwen3.5-9b", "messages": msgs, "tools": TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
d = json.dumps(body).encode()
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=d, headers={"Content-Type": "application/json"})
r = urllib.request.urlopen(req, timeout=200)
j = json.loads(r.read().decode())
ch = j["choices"][0]
print("finish:", ch.get("finish_reason"))
print("tool_calls:", json.dumps(ch["message"].get("tool_calls"), ensure_ascii=False))
if os.path.exists(r"D:\llama\test_output\report.pdf"):
    import subprocess
    print("PDF 产物:", os.path.getsize(r"D:\llama\test_output\report.pdf"), "B")
    # 回读验证
    d2 = json.dumps({"tool": "read_doc", "params": {"path": r"D:\llama\test_output\report.pdf"}}).encode()
    r2 = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d2, headers={"Content-Type": "application/json"}), timeout=60)
    print("回读:", json.loads(r2.read().decode()).get("content", "")[:120])
