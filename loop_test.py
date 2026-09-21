# -*- coding: utf-8 -*-
import urllib.request, json

TOOLS = [
    {"type": "function", "function": {"name": "stat_data", "description": "对表格文件（xlsx/csv/txt）做数据统计：按小时/按日期分组统计行数", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "group_by": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_doc", "description": "读取文档内容", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
]
sys_prompt = ("你是运行在用户电脑上的 AI 智能助手 Rui AI，可以像专业智能体一样自主操作这台电脑完成任务。可用工具：\n"
              "1. stat_data —— 表格数据统计（按小时/日期分组统计条数）\n"
              "2. read_doc —— 读取文档内容\n"
              "使用规则：\n"
              "- 用户上传的文件会在上下文里注明磁盘路径，需要进一步分析统计时，直接用该路径调用 stat_data/read_doc，不要自行猜测或编造路径。\n"
              "- 用户要\u201c统计每小时/每天多少条数据、按小时统计、看数据分布\u201d等需求时，用 stat_data 对表格文件做分组统计（第一列为时间），再基于统计结果回答。\n"
              "【用户上传的文件：<1.xlsx>，磁盘路径：D:\\llama\\uploads\\1.xlsx。文件内容不在此展开，需要读取或统计分析数据时，请务必用 read_doc / stat_data 工具读取该路径，不要询问用户。】")
user_msg = ("统计这个文件里每小时有多少条数据\n"
            "【你（Rui AI）必须处理以下已上传文件（无需再询问路径）：D:\\llama\\uploads\\1.xlsx。若用户要求统计/分析/总结其中的数据，请直接用 stat_data 或 read_doc 读取这些路径来完成，不要反问用户文件位置。】")

def chat(msgs):
    body = {"model": "qwen3.5-9b", "messages": msgs, "tools": TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
    d = json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=d, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=150)
    return json.loads(r.read().decode())

def exec_tool(name, args):
    d = json.dumps({"tool": name, "params": args}).encode()
    req = urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=60)
    return json.loads(r.read().decode())

msgs = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}]
for step in range(5):
    j = chat(msgs)
    ch = j["choices"][0]
    msg = ch["message"]
    fr = ch.get("finish_reason")
    if fr == "tool_calls" and msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            fn = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")
            print(f"[step {step}] CALL {fn} {json.dumps(args, ensure_ascii=False)}")
            result = exec_tool(fn, args)
            print(f"[step {step}] RESULT: {json.dumps(result, ensure_ascii=False)[:300]}")
            msgs.append({"role": "assistant", "content": None, "tool_calls": [tc]})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
    else:
        print(f"[step {step}] FINAL:", (msg.get("content") or "")[:1500])
        break
