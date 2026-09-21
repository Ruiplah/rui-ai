import urllib.request
import json

url = "http://127.0.0.1:8080/v1/chat/completions"
data = {
    "model": "gemma-4-12b",
    "messages": [
        {"role": "system", "content": "你是一个简洁的助手，用中文回答。"},
        {"role": "user", "content": "用三句话介绍一下你自己"}
    ],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": False}
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, timeout=180) as resp:
    result = json.loads(resp.read().decode('utf-8'))
    print("=== 回答 ===")
    print(result['choices'][0]['message']['content'])
    print(f"\nToken: {result['usage']}")
