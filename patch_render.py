import re

with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找并替换全量重渲染
old_pattern = r'store\.endTask\(\);\s*\n\s*ui\.renderMessages\(\);.*?\n\s*ui\.resetScrollState\(\);'
new_code = '''store.endTask();
      /* 生成完成后只更新最后一条助手消息（完整Markdown渲染），避免全量重渲染导致长对话卡顿 */
      const allBubbles = ui.els.messages.querySelectorAll(".msg.assistant .bubble");
      if (allBubbles.length && liveMsg.content) {
        const lastBubble = allBubbles[allBubbles.length - 1];
        try {
          lastBubble.innerHTML = '<div style="white-space:normal;word-break:break-word;line-height:1.6;">' + ui.renderMarkdown(liveMsg.content) + '</div>';
        } catch(e) {
          lastBubble.textContent = liveMsg.content;
        }
        ui.smartScrollToBottom();
      }
      ui.resetScrollState();'''

match = re.search(old_pattern, content, re.DOTALL)
if match:
    print(f'找到匹配，长度: {len(match.group(0))}')
    content = content.replace(match.group(0), new_code)
    print('✅ 已替换为增量渲染')
else:
    print('❌ 未找到匹配，尝试简单替换...')
    # 简单替换
    if 'ui.renderMessages();  /* 生成完成后全量重渲染' in content:
        content = content.replace(
            'ui.renderMessages();  /* 生成完成后全量重渲染，用完整版renderMarkdown渲染表格/标题等 */',
            '''/* 生成完成后只更新最后一条助手消息（完整Markdown渲染），避免全量重渲染 */
      const allBubbles = ui.els.messages.querySelectorAll(".msg.assistant .bubble");
      if (allBubbles.length && liveMsg.content) {
        const lastBubble = allBubbles[allBubbles.length - 1];
        try { lastBubble.innerHTML = '<div style="white-space:normal;word-break:break-word;line-height:1.6;">' + ui.renderMarkdown(liveMsg.content) + '</div>'; }
        catch(e) { lastBubble.textContent = liveMsg.content; }
        ui.smartScrollToBottom();
      }'''
        )
        print('✅ 简单替换成功')
    else:
        print('❌ 简单替换也失败')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

# 简单语法检查（括号匹配）
opens = content.count('{')
closes = content.count('}')
print(f'括号检查: {{={opens}, }}={closes}, 平衡={opens==closes}')
print('✅ 前端修改完成')
