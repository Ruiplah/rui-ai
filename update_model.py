import re

with open(r'D:\llama\agent_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换路径和名称
content = content.replace('gemma-4-12b-it-qat-q4_0.gguf', 'gemma-4-12B-it-Q4_K_M.gguf')
content = content.replace('Gemma 4 12B (QAT Q4_0)', 'Gemma 4 12B (Q4_K_M)')

with open(r'D:\llama\agent_server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
