import urllib.request, json, time

# 测试不同查询
url = 'http://127.0.0.1:8082/api/exec'

for query in ['Python教程', '理想MEGA', '人工智能最新进展']:
    data = {'tool': 'web_search', 'args': {'query': query, 'n': 3}}
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        elapsed = time.time() - start
        count = len(result.get('results', []))
        print(f"查询: {query}")
        print(f"  耗时: {elapsed:.1f}秒, 结果: {count}条")
        if count > 0:
            for i, r in enumerate(result['results'][:2]):
                print(f"    {i+1}. [{r.get('source','?')}] {r.get('title','')[:40]}")
        else:
            print(f"  返回内容: {str(result)[:100]}")
    except Exception as e:
        print(f"查询: {query}, 错误: {e}")
    print()
