# -*- coding: utf-8 -*-
"""验证完整 agent 工具循环：模型调用工具 -> 执行 -> 反馈 -> 最终回答"""
import json, urllib.request

MODEL = "http://127.0.0.1:8080/v1/chat/completions"
AGENT = "http://127.0.0.1:8082/api/exec"

TOOLS = [{
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "列出指定目录下的文件和文件夹",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "目录路径"}}, "required": ["path"]}
    }
}]

def chat(messages, tools=None):
    body = {"model": "qwen3.5-9b", "messages": messages,
            "chat_template_kwargs": {"enable_thinking": False}}
    if tools:
        body["tools"] = tools
    d = json.dumps(body).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request(MODEL, data=d, headers={"Content-Type": "application/json"}), timeout=180)
    return json.loads(r.read().decode("utf-8"))

def exec_tool(name, params):
    d = json.dumps({"tool": name, "params": params}).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request(AGENT, data=d, headers={"Content-Type": "application/json"}), timeout=60)
    return json.loads(r.read().decode("utf-8"))

msgs = [{"role": "user", "content": "D 盘根目录下有哪些文件夹？"}]
for step in range(5):
    resp = chat(msgs, TOOLS)
    msg = resp["choices"][0]["message"]
    fr = resp["choices"][0]["finish_reason"]
    print(f"--- step {step} finish_reason={fr}")
    if fr == "tool_calls" and msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            fn = tc["function"]
            args = json.loads(fn["arguments"] or "{}")
            print(f"  [工具调用] {fn['name']}({args})")
            result = exec_tool(fn["name"], args)
            # 精简结果给模型
            summary = result
            if fn["name"] == "list_dir" and "items" in result:
                names = [i["name"] + ("/" if i["type"] == "dir" else "") for i in result["items"][:50]]
                summary = {"count": result["count"], "items": names}
            print(f"  [结果] {str(summary)[:200]}")
            msgs.append({"role": "assistant", "content": "", "tool_calls": [tc]})
            msgs.append({"role": "tool", "content": json.dumps(summary, ensure_ascii=False), "tool_call_id": tc["id"]})
        continue
    else:
        print("最终回答:", msg.get("content", ""))
        break
