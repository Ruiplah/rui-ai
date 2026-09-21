import re

with open(r'D:\llama\agent_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修改LLAMA_CTX
content = content.replace('LLAMA_CTX = 32768', 'LLAMA_CTX = 16384  # 16K平衡速度与内存')

# 2. 在启动参数中添加GPU加速（在"--path", WEBUI_PATH,后面插入）
old = '"--path", WEBUI_PATH,\n        ], creationflags=CREATE_NO_WINDOW)'
new = '''"--path", WEBUI_PATH,
            "-ngl", "99",       # GPU加速：全部层卸载到显存（8GB显存可放下12B Q4模型）
            "-t", "12",          # CPU线程：i5-10600KF有12逻辑处理器
            "-tb", "12",         # batch线程：prefill阶段也用12线程
        ], creationflags=CREATE_NO_WINDOW)'''

if old in content:
    content = content.replace(old, new)
    print('✅ 启动参数已添加GPU加速')
else:
    print('❌ 未找到启动参数，尝试其他匹配...')
    # 用正则匹配
    pattern = r'("--path", WEBUI_PATH,\s*\], creationflags=CREATE_NO_WINDOW\))'
    match = re.search(pattern, content)
    if match:
        print(f'找到匹配: {match.group(0)[:80]}')
        content = content.replace(match.group(1), new)
        print('✅ 通过正则替换成功')
    else:
        print('❌ 正则也未找到')

with open(r'D:\llama\agent_server.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 语法校验
import py_compile
try:
    py_compile.compile(r'D:\llama\agent_server.py', doraise=True)
    print('✅ Python语法校验通过')
except py_compile.PyCompileError as e:
    print(f'❌ 语法错误: {e}')
