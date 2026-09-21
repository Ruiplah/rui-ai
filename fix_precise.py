"""精确修复：基于实际代码结构"""
import re

# ===== 后端：搜索缓存加线程锁 =====
with open(r'D:\llama\agent_server.py', 'r', encoding='utf-8') as f:
    b = f.read()

# 加线程锁
b = b.replace(
    '# 搜索缓存（避免频繁请求被反爬虫）\n_search_cache = {}\n_search_cache_time = {}',
    '# 搜索缓存（避免频繁请求被反爬虫，线程安全+LRU上限）\nimport threading as _st\n_search_cache_lock = _st.Lock()\n_search_cache = {}\n_search_cache_time = {}\n_SEARCH_CACHE_MAX = 200'
)

# 缓存读取加锁
b = b.replace(
    '    if cache_key in _search_cache and now - _search_cache_time.get(cache_key, 0) < 300:\n        return _search_cache[cache_key][:n]',
    '    with _search_cache_lock:\n        if cache_key in _search_cache and now - _search_cache_time.get(cache_key, 0) < 300:\n            return _search_cache[cache_key][:n]'
)

# 缓存写入加锁+LRU
b = b.replace(
    '    _search_cache[cache_key] = final\n    _search_cache_time[cache_key] = now',
    '    with _search_cache_lock:\n        # LRU：超过上限删除最旧\n        if len(_search_cache) >= _SEARCH_CACHE_MAX:\n            oldest = min(_search_cache_time, key=_search_cache_time.get)\n            del _search_cache[oldest]\n            del _search_cache_time[oldest]\n        _search_cache[cache_key] = final\n        _search_cache_time[cache_key] = now'
)

with open(r'D:\llama\agent_server.py', 'w', encoding='utf-8') as f:
    f.write(b)
print('✅ 后端搜索缓存已加线程锁+LRU')

# ===== 前端修复 =====
with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    f_content = f.read()

# 1. 确认弹窗加60秒超时（找实际代码）
confirm_match = re.search(r'confirmAction\(tool, args\)\s*\{[^}]*?new Promise', f_content)
if confirm_match:
    # 在new Promise后加定时器
    f_content = f_content.replace(
        'confirmAction(tool, args) {\n    return new Promise((resolve) => {\n      this._modalResolve = resolve;',
        'confirmAction(tool, args) {\n    return new Promise((resolve) => {\n      this._modalResolve = resolve;\n      // 60秒超时自动拒绝\n      this._confirmTimer = setTimeout(() => { if (this._modalResolve) { const r = this._modalResolve; this._modalResolve = null; this._modalOverlay.style.display = "none"; r(false); } }, 60000);'
    )
    print('✅ 确认弹窗已加60秒超时')
else:
    print('⚠️ 确认弹窗代码未找到')

# 2. 确认弹窗resolve清除定时器
f_content = f_content.replace(
    '_confirmResult(ok) {\n    if (this._modalResolve) {\n      const r = this._modalResolve;\n      this._modalResolve = null;\n      this._modalOverlay.style.display = "none";',
    '_confirmResult(ok) {\n    if (this._modalResolve) {\n      const r = this._modalResolve;\n      this._modalResolve = null;\n      if (this._confirmTimer) { clearTimeout(this._confirmTimer); this._confirmTimer = null; }\n      this._modalOverlay.style.display = "none";'
)
print('✅ 确认弹窗resolve已清除定时器')

# 3. 会话切换清理pending
f_content = f_content.replace(
    'switchConv(id) {\n    if (store.state.task && store.state.task.convId === store.state.currentConvId) {\n      store.state.task.abortCtrl.abort();\n    }\n    store.state.currentConvId = id;\n    ui._streamText = "";\n    ui._streamThink = "";',
    'switchConv(id) {\n    if (store.state.task && store.state.task.convId === store.state.currentConvId) {\n      store.state.task.abortCtrl.abort();\n    }\n    store.state.currentConvId = id;\n    ui._streamText = "";\n    ui._streamThink = "";\n    if (store._pendingInstructions) store._pendingInstructions.length = 0;'
)
print('✅ 会话切换已清理pending')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(f_content)
print('✅ 前端修复完成')

print('\n===== 修复完成 =====')
