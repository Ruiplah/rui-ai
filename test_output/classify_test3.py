import json, urllib.request

SYS = '''你是消息路由判断器。用户正在让 AI 执行一个任务，此时用户又发来一条新消息。判断这条新消息属于哪一类：
- INJECT：任务相关——继续/修改/补充/追加当前任务的要求、要求用工具处理文件/生成文档/统计数据、针对正在做的事提出新指令等。
- PROGRESS：询问当前任务进行到哪了、进度、完成没有、进行到第几步、卡在哪——只是想知道任务状态，不是新的执行指令。
- DIRECT：普通对话——闲聊、问候、与当前任务无关的独立提问（问日期、算数学、聊话题、情感交流等）、随口回应等。
只回复 INJECT 或 PROGRESS 或 DIRECT 三个词之一，不要输出其他任何内容。'''
task = r'读取 D:\llama\uploads\理想_1788182477619.xlsx 并统计每小时消息数量，生成报告'
tests = ['你好', '任务进程怎么样了', '进度如何', '今天几号', '继续统计', '把结果生成Excel', '谢谢', '你觉得我买的基金怎么样', '再帮我算一下平均', '1+1等于几', '把那个文件也分析一下', '嗯好的', '完成了吗', '现在到第几步了', '卡在哪里了']
for t in tests:
    body = {'model': 'qwen3.5-9b', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': '【当前正在执行的任务】' + task + '\n\n【用户刚发的新消息】' + t}], 'max_tokens': 8, 'temperature': 0, 'stream': False, 'chat_template_kwargs': {'enable_thinking': False}}
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=90))
        out = r['choices'][0]['message']['content'].strip().upper()
    except Exception as e:
        out = 'ERR:' + str(e)[:50]
    label = 'PROGRESS' if 'PROGRESS' in out else ('INJECT' if 'INJECT' in out else ('DIRECT' if 'DIRECT' in out else out))
    print(label, '|', t)
