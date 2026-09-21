with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 优化1：上下文截断从"16条"改为"最多3000字符"，避免长对话prefill暴增
old1 = '''    /* 上下文截断：只保留最近16条历史，避免长对话撑爆32K上下文 */
    const historyAll = conv.messages.slice(0,-1).map(m => ({role:m.role, content:m.content}));
    const history = historyAll.length > 16 ? historyAll.slice(-16) : historyAll;'''
new1 = '''    /* 上下文截断：按总字符数截断（最多3000字符），避免长散文/思考过程撑爆上下文导致prefill暴增 */
    const historyAll = conv.messages.slice(0,-1).map(m => ({role:m.role, content:m.content}));
    let history = historyAll;
    let totalChars = history.reduce((s,m) => s + (m.content?m.content.length:0), 0);
    while (history.length > 2 && totalChars > 3000) {
      history = history.slice(1);
      totalChars = history.reduce((s,m) => s + (m.content?m.content.length:0), 0);
    }'''

if old1 in content:
    content = content.replace(old1, new1)
    print('✅ 优化1: 上下文按字符数截断（3000字符）')
else:
    print('❌ 优化1未找到匹配')

# 优化2：普通模式自动联网搜索改为默认关闭（只在设置中开启时才搜）
# 在搜索判断前加设置检查
old2 = '''    let searchedCount = 0;
    if (!isSmallTalk(searchQuery)) {'''
new2 = '''    let searchedCount = 0;
    /* 普通模式自动联网搜索：默认关闭，避免每次提问都先爬搜索引擎导致等待几十秒。需要时在设置中开启 */
    const autoSearch = store.state.settings.autoSearch !== false;  // 默认关闭
    if (autoSearch && !isSmallTalk(searchQuery)) {'''

if old2 in content:
    content = content.replace(old2, new2)
    print('✅ 优化2: 普通模式自动搜索默认关闭')
else:
    print('❌ 优化2未找到匹配')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 普通模式速度优化完成')
