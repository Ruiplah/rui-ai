import urllib.request, json, time

def test(ctx_size, label):
    url = 'http://127.0.0.1:8080/v1/chat/completions'
    data = {
        'model': 'gemma-4-12b',
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'max_tokens': 50,
        'chat_template_kwargs': {'enable_thinking': False}
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start
    tokens = result['usage']['completion_tokens']
    print(f'{label}: {tokens} tokens / {elapsed:.1f}s = {tokens/elapsed:.2f} token/s')

test(16384, '当前(16K ctx)')
