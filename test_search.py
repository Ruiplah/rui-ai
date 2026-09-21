import urllib.request, json, time

# 测试后端搜索工具
url = 'http://127.0.0.1:8082/api/exec'
data = {
    'tool': 'web_search',
    'args': {'query': '今天广州天气', 'n': 3}
}

req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
start = time.time()
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start
    print(f"搜索耗时: {elapsed:.1f}秒")
    print(f"结果数量: {len(result.get('results', []))}")
    for i, r in enumerate(result.get('results', [])[:3]):
        print(f"  {i+1}. [{r.get('source','?')}] {r.get('title','')[:50]}")
        if r.get('snippet'):
            print(f"     摘要: {r['snippet'][:80]}")
except Exception as e:
    print(f"搜索错误: {e}")
