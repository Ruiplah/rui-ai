with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 撤销代码层面的强制停止逻辑
old = """        /* 代码层面强制停止：如果已经生成了有意义的最终回答，即使模型又输出工具调用也直接停止，不依赖模型自觉 */
        if (finish === "tool_calls" && toolCalls && toolCalls.length && stepCount >= 1 && liveMsg.content && liveMsg.content.trim().length > 30) {
          store.updateTask({ phase:"完成", step:stepCount });
          store.notify();
          return liveMsg.content.trim();
        }

        /* 如果是工具调用 */
        if (finish === "tool_calls" && toolCalls && toolCalls.length) {"""

new = """        /* 如果是工具调用 */
        if (finish === "tool_calls" && toolCalls && toolCalls.length) {"""

if old in content:
    content = content.replace(old, new)
    print('✅ 已撤销代码层面强制停止逻辑')
else:
    print('❌ 未找到匹配（可能已经撤销了）')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 修改完成')
