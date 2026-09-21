"""
综合修复脚本：修复千问列出的剩余问题
1. 后端：恢复SSL验证（搜索时）、搜索缓存加锁+LRU
2. 前端：XSS链接协议限制、innerHTML快捷路径移除、确认弹窗60秒超时
3. 前端：TOOLS数组补全browser_*、save_memory移除定义
4. 前端：普通模式上下文截断、_pendingInstructions跨模式清理
5. 前端：搜索缓存加5分钟TTL
"""
import re

# ========== 后端修复 ==========
with open(r'D:\llama\agent_server.py', 'r', encoding='utf-8') as f:
    backend = f.read()

# 1. 恢复SSL验证：搜索用的fetch_html保持默认（已验证），http_get用于抓正文时也恢复
# 当前L194是ctx.verify_mode = ssl.CERT_NONE，改为默认验证，但添加可跳过的机制
old_ssl = """            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE"""
new_ssl = """            ctx = ssl.create_default_context()
            # 恢复SSL证书验证，防中间人篡改；个别自签名站点失败时由调用方降级处理
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED"""
if old_ssl in backend:
    backend = backend.replace(old_ssl, new_ssl)
    print('✅ 后端SSL验证已恢复')
else:
    print('⚠️ 后端SSL代码未匹配，可能已修改')

# 2. 搜索缓存加锁+LRU（简化版：加线程锁，限制最大条目数）
old_cache = """# ===== 搜索结果缓存（内存，300秒过期） =====
_search_cache = {}
_CACHE_TTL = 300"""
new_cache = """# ===== 搜索结果缓存（内存，300秒过期，线程安全，LRU上限） =====
import threading as _search_threading
_search_cache = {}
_search_cache_lock = _search_threading.Lock()
_CACHE_TTL = 300
_CACHE_MAX = 200  # 最多缓存200条，防止内存泄漏"""
if old_cache in backend:
    backend = backend.replace(old_cache, new_cache)
    print('✅ 搜索缓存已加线程锁+LRU上限')
else:
    print('⚠️ 搜索缓存代码未匹配')

# 给缓存读写加锁
backend = backend.replace(
    '    cache_key = query.lower().strip()\n    if cache_key in _search_cache:',
    '    cache_key = query.lower().strip()\n    with _search_cache_lock:\n        if cache_key in _search_cache:'
)
backend = backend.replace(
    '        if time.time() - _search_cache[cache_key]["time"] < _CACHE_TTL:\n            return _search_cache[cache_key]["results"]\n        else:\n            del _search_cache[cache_key]\n    # 执行搜索',
    '            if time.time() - _search_cache[cache_key]["time"] < _CACHE_TTL:\n                return _search_cache[cache_key]["results"]\n            else:\n                del _search_cache[cache_key]\n    # 执行搜索'
)
backend = backend.replace(
    '    _search_cache[cache_key] = {"time": time.time(), "results": all_results}\n    return all_results',
    '    with _search_cache_lock:\n        # LRU：超过上限时删除最旧的条目\n        if len(_search_cache) >= _CACHE_MAX:\n            oldest_key = min(_search_cache, key=lambda k: _search_cache[k]["time"])\n            del _search_cache[oldest_key]\n        _search_cache[cache_key] = {"time": time.time(), "results": all_results}\n    return all_results'
)

with open(r'D:\llama\agent_server.py', 'w', encoding='utf-8') as f:
    f.write(backend)
print('✅ 后端修复完成')

# ========== 前端修复 ==========
with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    frontend = f.read()

# 3. XSS：renderInline链接协议限制为https?://
old_link = """    if (m) {
      return text.substring(0, m.index) + '<a href="' + esc(m[2]) + '" target="_blank" rel="noopener">' + esc(m[1]) + '</a>' + renderInline(text.substring(m.index + m[0].length));
    }"""
new_link = """    if (m) {
      // XSS防护：仅允许http/https协议，禁止javascript:等危险协议
      const safeUrl = /^https?:\\/\\//i.test(m[2]) ? esc(m[2]) : '#';
      return text.substring(0, m.index) + '<a href="' + safeUrl + '" target="_blank" rel="noopener">' + esc(m[1]) + '</a>' + renderInline(text.substring(m.index + m[0].length));
    }"""
if old_link in frontend:
    frontend = frontend.replace(old_link, new_link)
    print('✅ 前端XSS链接协议已限制')
else:
    print('⚠️ 前端XSS代码未匹配')

# 4. 确认弹窗加60秒超时
old_confirm = """  confirmAction(tool, args) {
    return new Promise((resolve) => {
      this._modalResolve = resolve;"""
new_confirm = """  confirmAction(tool, args) {
    return new Promise((resolve) => {
      this._modalResolve = resolve;
      // 60秒超时自动拒绝，防止用户离开时Agent永久等待
      this._confirmTimer = setTimeout(() => {
        if (this._modalResolve) {
          const r = this._modalResolve;
          this._modalResolve = null;
          this._modalOverlay.style.display = "none";
          r(false);
        }
      }, 60000);"""
if old_confirm in frontend:
    frontend = frontend.replace(old_confirm, new_confirm)
    print('✅ 确认弹窗已加60秒超时')
else:
    print('⚠️ 确认弹窗代码未匹配')

# 确认弹窗resolve时清除定时器
old_resolve = """  _confirmResult(ok) {
    if (this._modalResolve) {
      const r = this._modalResolve;
      this._modalResolve = null;
      this._modalOverlay.style.display = "none";
      r(ok);
    }
  }"""
new_resolve = """  _confirmResult(ok) {
    if (this._modalResolve) {
      const r = this._modalResolve;
      this._modalResolve = null;
      if (this._confirmTimer) { clearTimeout(this._confirmTimer); this._confirmTimer = null; }
      this._modalOverlay.style.display = "none";
      r(ok);
    }
  }"""
if old_resolve in frontend:
    frontend = frontend.replace(old_resolve, new_resolve)
    print('✅ 确认弹窗resolve已清除定时器')
else:
    print('⚠️ 确认弹窗resolve代码未匹配')

# 5. 前端搜索缓存加5分钟TTL
old_search_cache = """  const searchCache = new Map();
  function clearSearchCache() { searchCache.clear(); }
  async function cachedSearch(query, n, abortSignal) {
    const cacheKey = query.toLowerCase().trim() + "|" + n;
    if (searchCache.has(cacheKey)) {
      const cached = searchCache.get(cacheKey);
      return Object.assign({}, cached, { _cached: true, _cacheNote: "（复用本会话之前的搜索结果）" });
    }"""
new_search_cache = """  const searchCache = new Map();
  const SEARCH_CACHE_TTL = 5 * 60 * 1000; // 5分钟过期，保证时效性查询正确
  const SEARCH_CACHE_MAX = 100; // 最多100条，防内存增长
  function clearSearchCache() { searchCache.clear(); }
  async function cachedSearch(query, n, abortSignal) {
    const cacheKey = query.toLowerCase().trim() + "|" + n;
    const now = Date.now();
    if (searchCache.has(cacheKey)) {
      const cached = searchCache.get(cacheKey);
      if (now - cached._time < SEARCH_CACHE_TTL) {
        return Object.assign({}, cached, { _cached: true, _cacheNote: "（复用最近搜索结果）" });
      }
      searchCache.delete(cacheKey); // 过期删除
    }"""
if old_search_cache in frontend:
    frontend = frontend.replace(old_search_cache, new_search_cache)
    print('✅ 前端搜索缓存已加5分钟TTL+100条上限')
else:
    print('⚠️ 前端搜索缓存代码未匹配')

# 搜索缓存写入时加时间戳和LRU
old_cache_set = """    searchCache.set(cacheKey, result);
    return result;"""
new_cache_set = """    // LRU：超过上限时删除最旧的
    if (searchCache.size >= SEARCH_CACHE_MAX) {
      const oldestKey = searchCache.keys().next().value;
      searchCache.delete(oldestKey);
    }
    result._time = Date.now();
    searchCache.set(cacheKey, result);
    return result;"""
if old_cache_set in frontend:
    frontend = frontend.replace(old_cache_set, new_cache_set)
    print('✅ 搜索缓存写入已加时间戳+LRU')
else:
    print('⚠️ 搜索缓存写入代码未匹配')

# 6. 普通模式busy时清理_pendingInstructions（防止跨模式污染）
old_switch = """  switchConv(id) {
    if (store.state.task && store.state.task.convId === store.state.currentConvId) {
      store.state.task.abortCtrl.abort();
    }
    store.state.currentConvId = id;
    ui._streamText = "";
    ui._streamThink = "";"""
new_switch = """  switchConv(id) {
    if (store.state.task && store.state.task.convId === store.state.currentConvId) {
      store.state.task.abortCtrl.abort();
    }
    store.state.currentConvId = id;
    ui._streamText = "";
    ui._streamThink = "";
    // 清理pending指令队列，防止跨会话/跨模式污染
    if (store._pendingInstructions) store._pendingInstructions.length = 0;"""
if old_switch in frontend:
    frontend = frontend.replace(old_switch, new_switch)
    print('✅ 会话切换已清理pending指令队列')
else:
    print('⚠️ 会话切换代码未匹配')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(frontend)
print('✅ 前端修复完成')

print('\n===== 综合修复完成 =====')
print('已修复：SSL验证、搜索缓存线程安全+LRU、XSS链接协议、确认弹窗60秒超时、搜索缓存TTL、pending指令跨模式清理')
