import re
html = open(r'D:\llama\webui\index.html', encoding='utf-8').read()
print('总大小:', len(html))
m = re.search(r'<body.*?</body>', html, re.S)
b = m.group(0) if m else ''
ids = re.findall(r'id="([^"]+)"', b)
print('IDs:', ids)
print()
# 打印 main 布局部分（前 120 行 html 相关）
# 找到 html 的 <body> 后 4000 字符
idx = html.find('<body')
print('=== body 开头 3000 字符 ===')
print(html[idx:idx+3000])
