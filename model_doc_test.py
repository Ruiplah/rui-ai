# -*- coding: utf-8 -*-
"""模型能力测试：解析文档 + 按指令生成文档（完整 agent 循环）"""
import urllib.request, json, os, time

TOOLS = [
    {"type": "function", "function": {"name": "create_doc", "description": "创建 Word(.docx)、Excel(.xlsx)、PDF 或文本文档。docx 填文本内容；xlsx 内容每行代表一行表格、用制表符分隔单元格；pdf 建议用英文。扩展名决定格式。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_doc", "description": "读取文档内容：支持 Word(.docx)、Excel(.xlsx)、PDF 以及 txt/md/csv/json 等文本文件", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "stat_data", "description": "对表格文件（xlsx/csv/txt）做数据统计：按小时/按日期分组统计行数", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "group_by": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "查看目录", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
]
SYS = """你是运行在用户电脑上的 AI 智能助手 Rui AI，可以自主操作这台电脑完成任务。可用工具：
1. create_doc / read_doc —— 创建/读取文档（Word、Excel、PDF、文本）
2. stat_data —— 表格数据统计
3. list_dir —— 查看目录
使用规则：
- 用户要\u201c做文档/生成 Word/Excel/报表\u201d时，用 create_doc 创建对应文件（xlsx 内容用制表符分隔单元格）；用户要\u201c读文档/看文件内容\u201d时，用 read_doc 读取。
- 所有工具完成后，用清晰中文给出最终回答（创建文档后要告诉用户文件保存路径）。"""

def chat(msgs):
    body = {"model": "qwen3.5-9b", "messages": msgs, "tools": TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
    d = json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=d, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=180)
    return json.loads(r.read().decode())

def exec_tool(name, args):
    d = json.dumps({"tool": name, "params": args}).encode()
    req = urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=90)
    return json.loads(r.read().decode())

def run(user_text, max_steps=8):
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": user_text}]
    calls = []
    for step in range(max_steps):
        j = chat(msgs)
        ch = j["choices"][0]
        msg = ch["message"]
        fr = ch.get("finish_reason")
        if fr == "tool_calls" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except Exception:
                    args = {"raw": tc["function"]["arguments"]}
                calls.append({"step": step, "fn": fn, "args": args})
                result = exec_tool(fn, args)
                msgs.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
        else:
            return {"answer": msg.get("content") or "", "calls": calls}
    return {"answer": "(达到步数上限)", "calls": calls}

os.makedirs(r"D:\llama\test_output", exist_ok=True)
print("=" * 60)
print("【测试A-1】解析并总结 txt 文档")
# 先造一个 txt
with open(r"D:\llama\test_output\项目说明.txt", "w", encoding="utf-8") as f:
    f.write("Rui AI 本地助手项目\n\n本项目在 Windows 电脑上部署了 Qwen3.5-9B 量化模型，提供本地 AI 助手服务。\n主要功能：对话、联网搜索、文件读写、文档生成、股票基金查询、数据统计。\n技术栈：llama.cpp + Python + 内置浏览器界面。")
r = run("读取 D:\\llama\\test_output\\项目说明.txt 的内容，并总结这个项目是做什么的，用一句话概括")
print("工具调用:", [(c["fn"], c["args"]) for c in r["calls"]])
print("回答:", r["answer"][:400])

print("\n" + "=" * 60)
print("【测试A-2】解析并统计 xlsx 文档（复用 1.xlsx）")
r = run("读取 D:\\llama\\uploads\\1.xlsx 并用 stat_data 统计每小时数据量，简要告诉我最多和最少的时段")
print("工具调用:", [(c["fn"], c["args"]) for c in r["calls"]])
print("回答:", r["answer"][:400])

print("\n" + "=" * 60)
print("【测试B-1】按指令生成 Word 文档")
r = run("请生成一份 Word 文档，标题《月度工作汇报》，包含：本月完成（3条）、下月计划（2条）。保存到 D:\\llama\\test_output\\月度汇报.docx")
print("工具调用:", [(c["fn"], c["args"]) for c in r["calls"]])
print("回答:", r["answer"][:400])
if os.path.exists(r"D:\llama\test_output\月度汇报.docx"):
    rr = exec_tool("read_doc", {"path": r"D:\llama\test_output\月度汇报.docx"})
    print("产物验证（回读）:", rr.get("content", "")[:200].replace("\n", " | "))

print("\n" + "=" * 60)
print("【测试B-2】按指令生成 Excel 表格")
r = run("请生成一个 Excel 报价单 xlsx，列：产品、单价、数量、金额（金额=单价*数量自己算），5 行产品数据。保存到 D:\\llama\\test_output\\报价单完整.xlsx")
print("工具调用:", [(c["fn"], c["args"]) for c in r["calls"]])
print("回答:", r["answer"][:400])
if os.path.exists(r"D:\llama\test_output\报价单完整.xlsx"):
    rr = exec_tool("read_doc", {"path": r"D:\llama\test_output\报价单完整.xlsx"})
    print("产物验证（回读）:", rr.get("content", "")[:300].replace("\n", " | "))

print("\n" + "=" * 60)
print("【测试B-3】按指令生成 txt 笔记")
r = run("帮我生成一个 txt 文件，内容是 3 条购物清单，保存到 D:\\llama\\test_output\\购物清单.txt")
print("工具调用:", [(c["fn"], c["args"]) for c in r["calls"]])
print("回答:", r["answer"][:300])
if os.path.exists(r"D:\llama\test_output\购物清单.txt"):
    with open(r"D:\llama\test_output\购物清单.txt", encoding="utf-8") as f:
        print("产物验证（回读）:", f.read()[:200].replace("\n", " | "))
