# -*- coding: utf-8 -*-
import urllib.request, json, urllib.error

TOOLS = [
    {"type": "function", "function": {"name": "create_doc", "description": "创建文档", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_doc", "description": "读取文档内容", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "stat_data", "description": "表格数据统计：按小时/按日期分组统计行数", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "group_by": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "查看目录", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
]
SYS = ("你是运行在用户电脑上的 AI 智能助手 Rui AI。可用工具：\n"
       "1. create_doc / read_doc —— 创建/读取文档\n2. stat_data —— 表格数据统计\n3. list_dir —— 查看目录\n"
       "用户要\u201c统计每小时/每天多少条数据\u201d时，用 stat_data 对表格文件做分组统计。")
msgs = [{"role": "system", "content": SYS},
        {"role": "user", "content": "读取 D:\\llama\\uploads\\1.xlsx 并用 stat_data 统计每小时数据量，简要告诉我最多和最少的时段"}]
body = {"model": "qwen3.5-9b", "messages": msgs, "tools": TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
d = json.dumps(body).encode()
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=d, headers={"Content-Type": "application/json"})
try:
    r = urllib.request.urlopen(req, timeout=180)
    j = json.loads(r.read().decode())
    ch = j["choices"][0]
    print("finish:", ch.get("finish_reason"))
    print("tool_calls:", json.dumps(ch["message"].get("tool_calls"), ensure_ascii=False))
    print("content:", (ch["message"].get("content") or "")[:200])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode()[:800])
