import urllib.request, json, time

url = 'http://127.0.0.1:8082/api/exec'

for query in ['Python教程', '理想MEGA']:
    data = {'tool': 'web_search', 'params': {'query': query, 'n': 3}}
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        elapsed = time.time() - start
        count = len(result.get('results', []))
        print(f"查询: {query}")
        print(f"  耗时: {elapsed:.1f}秒, 结果: {count}条, ok={result.get('ok')}")
        if count > 0:
            for i, r in enumerate(result['results'][:2]):
                print(f"    {i+1}. [{r.get('source','?')}] {r.get('title','')[:50]}")
        else:
            print(f"  error: {result.get('error','无')}")
    except Exception as e:
        print(f"查询: {query}, 错误: {e}")
    print()
