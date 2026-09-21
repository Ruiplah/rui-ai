import urllib.request, json, time
url = 'http://127.0.0.1:8080/v1/chat/completions'
data = {
    'model': 'gemma-4-12b',
    'messages': [{'role': 'user', 'content': 'Write a short poem about spring.'}],
    'max_tokens': 80,
    'chat_template_kwargs': {'enable_thinking': False}
}
req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
start = time.time()
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read())
elapsed = time.time() - start
tokens = result['usage']['completion_tokens']
print(f'8K上下文+GPU: {tokens} tokens / {elapsed:.1f}s = {tokens/elapsed:.2f} token/s')
