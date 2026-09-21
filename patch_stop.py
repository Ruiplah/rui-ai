with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 在【禁止行为】部分添加强制停止指令
old = """【禁止行为】
- 绝对不要输出思考过程、分析推理、规划步骤
- 绝对不要不搜索就回答事实性问题
- 绝对不要同一个关键词反复搜索超过2次
- 绝对不要搜索/调用工具超过6次还不回答
- 绝对不要凭记忆编造不确定的信息
- 绝对不要陷入重复循环"""

new = """【禁止行为】
- 绝对不要输出思考过程、分析推理、规划步骤
- 绝对不要不搜索就回答事实性问题
- 绝对不要同一个关键词反复搜索超过2次
- 绝对不要搜索/调用工具超过6次还不回答
- 绝对不要凭记忆编造不确定的信息
- 绝对不要陷入重复循环
- 【最重要】给出最终回答后立即停止，绝对不要继续思考、验证或调用工具。回答就是终点，不要画蛇添足"""

if old in content:
    content = content.replace(old, new)
    print('✅ 已添加强制停止指令')
else:
    print('❌ 未找到匹配')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 修改完成')
