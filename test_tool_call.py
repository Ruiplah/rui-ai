import urllib.request, json, time

url = 'http://127.0.0.1:8080/v1/chat/completions'

# 测试工具调用
data = {
    'model': 'gemma-4-12b',
    'messages': [
        {'role': 'system', 'content': '你是一个助手，可以使用计算器工具。当用户要求计算时，必须调用calculator工具。'},
        {'role': 'user', 'content': '用计算器算一下 1234 * 5678 等于多少'}
    ],
    'tools': [
        {
            'type': 'function',
            'function': {
                'name': 'calculator',
                'description': '执行数学计算',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'expression': {'type': 'string', 'description': '数学表达式'}
                    },
                    'required': ['expression']
                }
            }
        }
    ],
    'tool_choice': 'auto',
    'max_tokens': 500,
    'chat_template_kwargs': {'enable_thinking': False}
}

req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
start = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start
    print(f"耗时: {elapsed:.1f}秒")
    print(f"finish_reason: {result['choices'][0].get('finish_reason')}")
    
    msg = result['choices'][0]['message']
    print(f"有tool_calls: {'tool_calls' in msg and msg['tool_calls']}")
    if 'tool_calls' in msg and msg['tool_calls']:
        for tc in msg['tool_calls']:
            print(f"  工具: {tc['function']['name']}")
            print(f"  参数: {tc['function']['arguments']}")
    if msg.get('content'):
        print(f"内容: {msg['content'][:200]}")
except Exception as e:
    print(f"错误: {e}")
