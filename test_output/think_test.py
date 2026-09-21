import json, urllib.request

def ask(thinking):
    body = {'model': 'qwen3.5-9b', 'messages': [{'role': 'user', 'content': '一辆火车从广州开往北京，全程约2300公里，平均时速120公里/小时，中途停靠累计1.5小时，全程需要多少小时？'}], 'max_tokens': 300, 'temperature': 0.3, 'stream': False, 'chat_template_kwargs': {'enable_thinking': thinking}}
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    m = r['choices'][0]['message']
    rc = m.get('reasoning_content') or ''
    return rc, m.get('content') or ''

print("=== 思考模式 ON ===")
try:
    rc, c = ask(True)
    print("reasoning_content 长度:", len(rc))
    print("推理前80字:", (rc[:80].replace('\n', ' ')))
    print("回答:", c[:80].replace('\n', ' '))
except Exception as e:
    print("ERR:", e)

print()
print("=== 思考模式 OFF ===")
try:
    rc, c = ask(False)
    print("reasoning_content 长度:", len(rc))
    print("推理前80字:", (rc[:80].replace('\n', ' ')))
    print("回答:", c[:80].replace('\n', ' '))
except Exception as e:
    print("ERR:", e)
