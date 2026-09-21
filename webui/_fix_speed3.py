s = open(r'D:\llama\webui\index.html', encoding='utf-8').read()

# 修改 Agent 模式的 onToken 回调，添加速度计算
old_agent_token = '''onToken: (c) => { liveMsg.content = c; ui.streamUpdate(c); ui.updateStatusOnly(); },'''

new_agent_token = '''onToken: (c) => {
            liveMsg.content = c; ui.streamUpdate(c); ui.updateStatusOnly();
            /* 实时速度计算 */
            if (!store.state.genStartTime) { store.state.genStartTime = Date.now(); store.state.genTokens = 0; }
            store.state.genTokens++;
            const elapsed = (Date.now() - store.state.genStartTime) / 1000;
            if (elapsed > 0.5) { store.state.genSpeed = store.state.genTokens / elapsed; ui.updateStatusOnly(); }
          },'''

if old_agent_token in s:
    s = s.replace(old_agent_token, new_agent_token)
    print('Agent 模式速度计算添加完成')
else:
    print('未找到 Agent onToken')

# 修改普通模式的 onToken 回调
old_normal_token = 'onToken: (c) => { liveMsg.content = c; ui.streamUpdate(c); ui.updateStatusOnly(); },'
# 普通模式可能有不同的上下文，让我检查一下
if old_normal_token in s:
    s = s.replace(old_normal_token, new_agent_token, 1)  # 只替换第一个（Agent），第二个手动处理
    print('注意：普通模式 onToken 需要单独处理')
else:
    print('普通模式 onToken 格式不同')

open(r'D:\llama\webui\index.html', 'w', encoding='utf-8').write(s)
