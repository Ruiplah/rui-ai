# -*- coding: utf-8 -*-
"""模型生成文档测试（带重试）"""
import urllib.request, json, os, time, urllib.error

TOOLS = [
    {"type": "function", "function": {"name": "create_doc", "description": "创建 Word(.docx)、Excel(.xlsx)、PDF 或文本文档。docx 填文本内容；xlsx 内容每行代表一行表格、用制表符分隔单元格；pdf 建议用英文。扩展名决定格式。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_doc", "description": "读取文档内容：支持 Word(.docx)、Excel(.xlsx)、PDF 以及 txt/md/csv/json 等文本文件", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
]
SYS = ("你是运行在用户电脑上的 AI 智能助手 Rui AI。可用工具：\n"
       "1. create_doc / read_doc —— 创建/读取文档（Word、Excel、PDF、文本）\n"
       "使用规则：用户要\u201c做文档/生成 Word/Excel/报表\u201d时，用 create_doc 创建对应文件（xlsx 内容用制表符分隔单元格）；创建文档后告诉用户文件保存路径。")

def chat(msgs, retries=3):
    body = {"model": "qwen3.5-9b", "messages": msgs, "tools": TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
    d = json.dumps(body).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=d, headers={"Content-Type": "application/json"})
            r = urllib.request.urlopen(req, timeout=200)
            return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:200]
            if e.code == 400 and "context" in msg:
                raise
            time.sleep(4)
        except Exception:
            time.sleep(4)
    raise RuntimeError("chat failed after retries")

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

def check(path, substr=None):
    if not os.path.exists(path):
        return f"❌ 文件不存在: {path}"
    size = os.path.getsize(path)
    txt = ""
    try:
        rr = exec_tool("read_doc", {"path": path})
        txt = rr.get("content", "")
    except Exception as e:
        txt = f"(回读失败: {e})"
    ok = "✅" if (substr is None or substr in txt) else "⚠️"
    return f"{ok} 大小={size}B 内容含目标: {substr is None or substr in txt} | {txt[:180].replace(chr(10),' | ')}"

tests = [
    ("B-1 Word", "请生成一份 Word 文档，标题《月度工作汇报》，包含：本月完成（写3条）、下月计划（写2条）。保存到 D:\\llama\\test_output\\月度汇报.docx", r"D:\llama\test_output\月度汇报.docx", "月度工作汇报"),
    ("B-2 Excel", "请生成一个 Excel 报价单 xlsx，列：产品、单价、数量、金额（金额=单价*数量自己算），5 行产品数据。保存到 D:\\llama\\test_output\\报价单完整.xlsx", r"D:\llama\test_output\报价单完整.xlsx", "产品"),
    ("B-3 txt", "帮我生成一个 txt 文件，内容是 3 条购物清单，保存到 D:\\llama\\test_output\\购物清单.txt", r"D:\llama\test_output\购物清单.txt", "清单"),
]
for name, prompt, path, sub in tests:
    print("=" * 50)
    print(f"【{name}】{prompt[:50]}...")
    t0 = time.time()
    r = run(prompt)
    print(f"  用时 {int(time.time()-t0)}s 调用: {[(c['fn']) for c in r['calls']]}")
    print("  回答:", r["answer"][:250].replace("\n", " "))
    print("  产物:", check(path, sub))
