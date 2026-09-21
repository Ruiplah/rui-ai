import urllib.request, json, time
url = 'http://127.0.0.1:8080/v1/chat/completions'
data = {
    'model': 'gemma-4-12b',
    'messages': [{'role': 'user', 'content': 'Write a short poem about autumn, no more than 4 lines.'}],
    'max_tokens': 100,
    'chat_template_kwargs': {'enable_thinking': False}
}
req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
start = time.time()
with urllib.request.urlopen(req, timeout=300) as resp:
    result = json.loads(resp.read())
elapsed = time.time() - start
tokens = result['usage']['completion_tokens']
print(f'GPU全量卸载: {tokens} tokens / {elapsed:.1f}s = {tokens/elapsed:.2f} token/s')
print(f'首token延迟: 约{elapsed:.1f}s')
print(f'回答: {result["choices"][0]["message"]["content"][:150]}')
