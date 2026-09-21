#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rui AI Agent 能力实测（三模型适配验证）"""
import json
import re
import sys
import time
import urllib.request
import urllib.error

LLAMA = "http://127.0.0.1:8080"
AGENT = "http://127.0.0.1:8082"


def post(path, body, base=LLAMA, timeout=180):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)[:300]


def chat_nonstream(messages, tools=None, model="rui", max_tokens=8192, thinking=True, timeout=180):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens,
            "stream": False, "chat_template_kwargs": {"enable_thinking": thinking}}
    if tools:
        body["tools"] = tools
    st, raw = post("/v1/chat/completions", body, timeout=timeout)
    if st != 200:
        return {"_error": f"HTTP {st}", "_raw": raw[:600]}
    try:
        return json.loads(raw)
    except Exception as e:
        return {"_error": f"JSON解析失败: {e}", "_raw": raw[:600]}


def exec_tool(tool, params, timeout=60):
    body = json.dumps({"tool": tool, "params": params}).encode("utf-8")
    req = urllib.request.Request(AGENT + "/api/exec", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"error": str(e)[:200]}


def get_model_info():
    try:
        with urllib.request.urlopen(LLAMA + "/v1/models", timeout=5) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return d.get("data", [{}])[0].get("id", "?")
    except Exception as e:
        return f"?({e})"


# 复刻前端 TOOLS（28个）
FRONTEND_TOOLS = [
    {"type":"function","function":{"name":"get_time","description":"获取当前系统日期和时间","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"list_dir","description":"列出目录下的文件和子目录","parameters":{"type":"object","properties":{"path":{"type":"string","description":"目录路径"}},"required":["path"]}}},
    {"type":"function","function":{"name":"read_file","description":"读取文本文件内容","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"写入文本文件（覆盖）","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"create_doc","description":"创建Word文档(.docx)","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"create_excel","description":"创建Excel表格(.xlsx)","parameters":{"type":"object","properties":{"path":{"type":"string"},"headers":{"type":"array"},"rows":{"type":"array"},"sheet_name":{"type":"string"}},"required":["path","headers","rows"]}}},
    {"type":"function","function":{"name":"read_doc","description":"读取Word/Excel/PDF等文档内容","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"stat_data","description":"统计分析Excel/CSV数据","parameters":{"type":"object","properties":{"path":{"type":"string"},"group_by":{"type":"string"},"agg_col":{"type":"string"},"agg":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"run_command","description":"执行系统命令","parameters":{"type":"object","properties":{"cmd":{"type":"string"},"timeout":{"type":"number"}},"required":["cmd"]}}},
    {"type":"function","function":{"name":"calculator","description":"数学计算","parameters":{"type":"object","properties":{"expr":{"type":"string"}},"required":["expr"]}}},
    {"type":"function","function":{"name":"file_copy","description":"复制文件","parameters":{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]}}},
    {"type":"function","function":{"name":"file_move","description":"移动/重命名文件","parameters":{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]}}},
    {"type":"function","function":{"name":"file_delete","description":"删除文件","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"clipboard_get","description":"读取剪贴板内容","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"clipboard_set","description":"写入剪贴板","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
    {"type":"function","function":{"name":"screenshot","description":"截屏","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"ocr_image","description":"识别图片中的文字","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"image_info","description":"获取图片信息","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"system_info","description":"获取系统信息","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"save_memory","description":"保存一条长期记忆","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
    {"type":"function","function":{"name":"web_search","description":"联网搜索获取最新信息和事实","parameters":{"type":"object","properties":{"query":{"type":"string"},"n":{"type":"number"}},"required":["query"]}}},
    {"type":"function","function":{"name":"fetch_url","description":"抓取指定网页的完整正文内容","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"feishu_read_doc","description":"读取飞书在线文档","parameters":{"type":"object","properties":{"document_id":{"type":"string"}},"required":["document_id"]}}},
    {"type":"function","function":{"name":"feishu_list_tables","description":"列出飞书多维表格数据表","parameters":{"type":"object","properties":{"app_token":{"type":"string"}},"required":["app_token"]}}},
    {"type":"function","function":{"name":"feishu_read_records","description":"读取飞书多维表格记录","parameters":{"type":"object","properties":{"app_token":{"type":"string"},"table_id":{"type":"string"},"page_size":{"type":"number"}},"required":["app_token","table_id"]}}},
    {"type":"function","function":{"name":"feishu_search_records","description":"搜索飞书多维表格记录","parameters":{"type":"object","properties":{"app_token":{"type":"string"},"table_id":{"type":"string"},"filter":{"type":"object"},"page_size":{"type":"number"}},"required":["app_token","table_id"]}}},
    {"type":"function","function":{"name":"feishu_create_record","description":"向飞书多维表格新增记录","parameters":{"type":"object","properties":{"app_token":{"type":"string"},"table_id":{"type":"string"},"fields":{"type":"object"}},"required":["app_token","table_id","fields"]}}},
    {"type":"function","function":{"name":"feishu_update_record","description":"更新飞书多维表格记录","parameters":{"type":"object","properties":{"app_token":{"type":"string"},"table_id":{"type":"string"},"record_id":{"type":"string"},"fields":{"type":"object"}},"required":["app_token","table_id","record_id","fields"]}}},
]

# 复刻前端 system prompt（简化为等价长度，用于测量 token 占用）
import io
with io.open("D:\\llama\\webui\\index.html", "r", encoding="utf-8", errors="replace") as f:
    html = f.read()
m = re.search(r"let sys = `([\s\S]*?)`;", html)
REAL_SYS_PROMPT = m.group(1) if m else "（未提取到）"

RESULTS = []
def record(name, passed, detail=""):
    RESULTS.append((name, passed, str(detail)))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        for line in str(detail).split("\n")[:14]:
            print(f"        {line}")


MODEL_ID = get_model_info()
print("=" * 72)
print(f"当前测试模型: {MODEL_ID}")
print("=" * 72)

print()
print("--- T1 上下文预算分析（关键）---")
sys_chars = len(REAL_SYS_PROMPT)
tools_json = json.dumps(FRONTEND_TOOLS, ensure_ascii=False)
tools_chars = len(tools_json)
# 用 tokenizer 精确测量
st, raw = post("/tokenize", {"content": REAL_SYS_PROMPT})
sys_tokens = len(json.loads(raw).get("tokens", [])) if st == 200 else int(sys_chars * 0.6)
st, raw = post("/tokenize", {"content": tools_json})
tools_tokens = len(json.loads(raw).get("tokens", [])) if st == 200 else int(tools_chars * 0.35)
total_fixed = sys_tokens + tools_tokens
CTX = 8192
MAX_TOKENS = 8192
remaining = CTX - total_fixed
record("T1 上下文预算是否够用", remaining > 2000,
       f"llama-server -c = {CTX}  (后端 LLAMA_CTX)\n"
       f"前端 max_tokens = {MAX_TOKENS}\n"
       f"system prompt: {sys_chars} 字符 = {sys_tokens} tokens\n"
       f"28个工具定义: {tools_chars} 字符 = {tools_tokens} tokens\n"
       f"固定开销合计 = {total_fixed} tokens ({total_fixed*100//CTX}% of ctx)\n"
       f"剩余可用于对话+输出 = {remaining} tokens\n"
       f"-> {'✅ 充足' if remaining > 2000 else '❌ 严重不足：max_tokens(8192) >= ctx(8192)，无空间给对话历史'}")

print()
print("--- T2 max_tokens 超上下文时服务端行为 ---")
st, raw = post("/v1/chat/completions",
               {"model": "x", "messages": [{"role": "user", "content": "你好"}],
                "max_tokens": 8192, "stream": False}, timeout=120)
record("T2 max_tokens=8192 是否被服务端接受", st == 200,
       f"status={st}\n{raw[:300] if st != 200 else '请求成功（服务端会自动裁剪，但前端无从得知）'}")

print()
print("--- T3 基础对话能力 ---")
t0 = time.time()
r = chat_nonstream([{"role": "user", "content": "用一句话介绍你自己"}], thinking=True)
el = time.time() - t0
if "_error" in r:
    record("T3 基础对话", False, r)
else:
    ch = r.get("choices", [{}])[0]
    msg = ch.get("message", {})
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    usage = r.get("usage", {})
    tps = usage.get("completion_tokens", 0) / el if el > 0 else 0
    record("T3 基础对话", bool(content.strip()),
           f"耗时 {el:.1f}s, 速度 {tps:.1f} tok/s\n"
           f"content长度={len(content)}, reasoning长度={len(reasoning)}\n"
           f"usage={usage}\n回答: {content[:120]}")

print()
print("--- T4 enable_thinking=true 思考通道适配 ---")
r = chat_nonstream([{"role": "user", "content": "9.11和9.9哪个大？简要说明"}], thinking=True)
if "_error" in r:
    record("T4 思考模式开启", False, r)
else:
    msg = r.get("choices", [{}])[0].get("message", {})
    reasoning = msg.get("reasoning_content") or ""
    content = msg.get("content") or ""
    record("T4 思考模式开启", True,
           f"reasoning_content 长度={len(reasoning)}\n"
           f"content 长度={len(content)}\n"
           f"finish_reason={r.get('choices',[{}])[0].get('finish_reason')}\n"
           f"-> {'✅ 有独立思考通道' if reasoning else '⚠️ 无 reasoning_content 字段（前端思考面板将为空）'}\n"
           f"content预览: {content[:150]}")

print()
print("--- T5 enable_thinking=false 关闭思考适配 ---")
r = chat_nonstream([{"role": "user", "content": "9.11和9.9哪个大？"}], thinking=False)
if "_error" in r:
    record("T5 思考模式关闭", False, r)
else:
    msg = r.get("choices", [{}])[0].get("message", {})
    reasoning = msg.get("reasoning_content") or ""
    content = msg.get("content") or ""
    record("T5 思考模式关闭", bool(content.strip()) and not reasoning,
           f"reasoning长度={len(reasoning)}, content长度={len(content)}\n"
           f"-> {'✅ 正确关闭' if not reasoning else '❌ 关闭无效，仍有思考输出'}\n"
           f"content预览: {content[:150]}")

print()
print("--- T6 工具调用能力（Agent 核心）---")
t0 = time.time()
r = chat_nonstream([
    {"role": "system", "content": REAL_SYS_PROMPT[:6000]},
    {"role": "user", "content": "现在几点了？"}
], tools=FRONTEND_TOOLS, thinking=True, timeout=240)
el = time.time() - t0
if "_error" in r:
    record("T6 工具调用", False, r)
else:
    ch = r.get("choices", [{}])[0]
    msg = ch.get("message", {})
    tcs = msg.get("tool_calls") or []
    record("T6 工具调用触发", len(tcs) > 0,
           f"耗时 {el:.1f}s, finish_reason={ch.get('finish_reason')}\n"
           f"tool_calls数量={len(tcs)}\n"
           f"{'详情: ' + json.dumps(tcs, ensure_ascii=False)[:400] if tcs else '❌ 模型未调用工具，直接回答: ' + (msg.get('content') or '')[:150]}")

print()
print("--- T7 tool_calls 结构完整性（前端增量拼接依赖）---")
if "_error" not in r:
    tcs = r.get("choices", [{}])[0].get("message", {}).get("tool_calls") or []
    if tcs:
        tc = tcs[0]
        has_id = bool(tc.get("id"))
        has_name = bool(tc.get("function", {}).get("name"))
        args_raw = tc.get("function", {}).get("arguments", "")
        try:
            args = json.loads(args_raw)
            args_ok = True
            args_err = ""
        except Exception as e:
            args = None
            args_ok = False
            args_err = str(e)
        record("T7 tool_call 结构", has_id and has_name and args_ok,
               f"id={tc.get('id')!r} (前端需要它作为 tool_call_id 回传)\n"
               f"name={tc.get('function',{}).get('name')!r}\n"
               f"arguments={args_raw!r}\n"
               f"-> id{'✅' if has_id else '❌缺失(前端回传会失败)'} "
               f"name{'✅' if has_name else '❌'} "
               f"args{'✅可解析' if args_ok else '❌解析失败:'+args_err}")
        # 实际执行该工具
        if args_ok and has_name:
            name = tc["function"]["name"]
            res = exec_tool(name, args)
            record("T7b 工具实际执行", "error" not in res or res.get("need_confirm"),
                   f"执行 {name}({args}) -> {str(res)[:250]}")
    else:
        record("T7 tool_call 结构", False, "无 tool_calls 可验证")
else:
    record("T7 tool_call 结构", False, r)

print()
print("--- T8 多工具并行调用（前端 L1377 let result 声明在循环外的问题）---")
r2 = chat_nonstream([
    {"role": "system", "content": REAL_SYS_PROMPT[:6000]},
    {"role": "user", "content": "请同时告诉我现在几点，以及 D:\\llama 目录下有哪些文件。两个都要查。"}
], tools=FRONTEND_TOOLS, thinking=True, timeout=240)
if "_error" not in r2:
    tcs2 = r2.get("choices", [{}])[0].get("message", {}).get("tool_calls") or []
    record("T8 多工具并行调用", True,
           f"返回 tool_calls 数量 = {len(tcs2)}\n"
           + ("\n".join(f"  [{i}] {t.get('function',{}).get('name')} args={t.get('function',{}).get('arguments','')[:60]}" for i, t in enumerate(tcs2)) if tcs2 else "")
           + f"\n-> {'⚠️ 模型会并行返回多个 tool_calls，前端循环内 result 赋值在 let 声明之前会触发 TDZ ReferenceError 崩溃' if len(tcs2) > 1 else '本次仅1个，未触发崩溃路径'}")
else:
    record("T8 多工具并行调用", False, r2)

print()
print("--- T9 联网搜索 + 抓取 端到端协同 ---")
sr = exec_tool("web_search", {"query": "llama.cpp 是什么", "n": 3})
cnt = len(sr.get("results", []))
first_url = sr["results"][0]["url"] if cnt else ""
record("T9a 搜索可用", cnt > 0, f"返回 {cnt} 条, ok={sr.get('ok')}")
if first_url:
    fr = exec_tool("fetch_url", {"url": first_url})
    record("T9b 抓取搜索到的网页", bool(fr.get("ok")) and fr.get("chars", 0) > 100,
           f"URL: {first_url}\n结果: {str(fr)[:300]}\n"
           f"-> {'✅ 搜索→抓取链路通畅' if fr.get('ok') else '❌ 链路断裂：能搜到但抓不了正文，模型只能靠 snippet 作答'}")

print()
print("--- T10 完整 Agent 循环模拟（复刻前端 run 逻辑）---")
msgs = [{"role": "system", "content": REAL_SYS_PROMPT[:6000]},
        {"role": "user", "content": "帮我算一下 (123*456)+789 等于多少，用计算器工具"}]
final_answer = ""
loop_log = []
for step in range(6):
    rr = chat_nonstream(msgs, tools=FRONTEND_TOOLS, thinking=True, timeout=240)
    if "_error" in rr:
        loop_log.append(f"step{step}: 模型调用失败 {rr}")
        break
    ch = rr.get("choices", [{}])[0]
    msg = ch.get("message", {})
    tcs = msg.get("tool_calls") or []
    if ch.get("finish_reason") == "tool_calls" and tcs:
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tcs})
        for tc in tcs:
            fn = tc.get("function", {})
            nm = fn.get("name", "")
            try:
                ar = json.loads(fn.get("arguments") or "{}")
            except Exception:
                ar = {}
            res = exec_tool(nm, ar)
            loop_log.append(f"step{step}: {nm}({json.dumps(ar,ensure_ascii=False)[:70]}) -> {str(res)[:90]}")
            msgs.append({"role": "tool", "content": json.dumps(res, ensure_ascii=False)[:8000],
                         "tool_call_id": tc.get("id")})
        continue
    final_answer = msg.get("content") or ""
    loop_log.append(f"step{step}: 模型给出最终回答 ({len(final_answer)}字)")
    break
record("T10 Agent 循环", bool(final_answer.strip()) and any("calculator" in l for l in loop_log),
       "\n".join(loop_log) + f"\n最终回答: {final_answer[:250]}")

print()
print("--- T11 token 消耗实测（前端估算 *0.6 是否准确）---")
if "_error" not in r:
    u = r.get("usage", {})
    prompt_tok = u.get("prompt_tokens", 0)
    # 前端估算方式
    est_msgs = [{"role": "user", "content": "9.11和9.9哪个大？简要说明"}]
    est_len = sum(len(m.get("content", "")) for m in est_msgs)
    est_tok = int(est_len * 0.6)
    comp = u.get("completion_tokens", 0)
    est_comp = int(len(r.get("choices",[{}])[0].get("message",{}).get("content","")) * 0.6)
    record("T11 token 估算准确度", False,
           f"真实 prompt_tokens={prompt_tok}, 前端估算={est_tok}\n"
           f"真实 completion_tokens={comp}, 前端估算={est_comp}\n"
           f"-> 前端 len*0.6 估算仅用于 usage 缺失时，实际 usage 通常存在")

print()
print("=" * 72)
print("汇总")
print("=" * 72)
print(f"通过 {sum(1 for _,p,_ in RESULTS if p)}/{len(RESULTS)}")
for n, p, d in RESULTS:
    if not p:
        print(f"\n✗ {n}")
        for line in d.split("\n")[:6]:
            print(f"    {line}")

print("\nJSON_RESULT_START")
print(json.dumps({"model": MODEL_ID, "results": [{"name": n, "pass": p, "detail": d[:800]} for n, p, d in RESULTS]}, ensure_ascii=False))
print("JSON_RESULT_END")
