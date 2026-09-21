# -*- coding: utf-8 -*-
"""端到端测试：联网搜索 -> 抓取 -> 喂给本地模型"""
import json
import urllib.parse
import urllib.request

SEARCH = "http://127.0.0.1:8081/api/search"
FETCH = "http://127.0.0.1:8081/api/fetch"
MODEL = "http://127.0.0.1:8080/v1/chat/completions"

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

# 1) 搜索一个时效性问题
q = "2026年8月有什么重要新闻"
print("== 搜索：", q)
data = get(SEARCH + "?q=" + urllib.parse.quote(q) + "&n=4")
results = data.get("results", [])
print("命中", len(results), "条")
for i, r in enumerate(results):
    print(f"  {i+1}. {r['title']}  {r['url']}")

# 2) 抓取前2条正文
context = []
for i, r in enumerate(results[:2]):
    try:
        pg = get(FETCH + "?url=" + urllib.parse.quote(r["url"]))
        body = (pg.get("text") or "")[:1500]
        context.append(f"来源{i+1}：《{r['title']}》 网址:{r['url']}\n{body}")
        print(f"  已抓取来源{i+1}: {pg.get('title','')}")
    except Exception as e:
        context.append(f"来源{i+1}：《{r['title']}》 网址:{r['url']}\n{r.get('snippet','')}")
        print(f"  来源{i+1}抓取失败，用摘要: {e}")

# 3) 组装消息喂给模型
sys_content = "以下是联网搜索到的资料（搜索时间：2026-08-31）：\n" + "\n\n".join(context) + "\n\n请优先依据以上资料回答；资料不足请说明。"
payload = {
    "model": "qwen3.5-9b",
    "messages": [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": q}
    ],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": False}
}
print("\n== 调用本地模型 ...")
req = urllib.request.Request(MODEL, data=json.dumps(payload).encode("utf-8"),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    resp = json.loads(r.read().decode("utf-8"))
content = resp["choices"][0]["message"]["content"]
print("== 模型回答 ==")
print(content)
