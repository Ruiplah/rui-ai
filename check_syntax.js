
"use strict";
/* ============================================================
   Rui AI v3 — 完整版
   架构：Store（单一数据源）+ Agent Engine（ReAct循环）+ UI Renderer（数据驱动）
   ============================================================ */

/* ================= 常量 ================= */
const MODEL = "qwen3.5-9b";
let currentModelThinking = true;  // 当前模型是否支持思考模式（Gemma 4 需关闭）
/* 动态获取主机地址：手机访问局域网IP时自动使用对应IP，本机访问时用127.0.0.1 */
const AGENT_API = location.hostname && location.hostname !== "localhost" && location.hostname !== "127.0.0.1" ? "http://" + location.hostname + ":8082" : "http://127.0.0.1:8082";
const ACCESS_TOKEN = "";  /* 与后端 RUI_ACCESS_TOKEN 环境变量一致；留空则后端不强制校验（向后兼容） */
const MAX_STEPS_DEFAULT = 30;

/* ================= 工具定义 ================= */
const TOOLS = [{type:"function",function:{name:"get_time",description:"获取当前系统日期和时间",parameters:{type:"object",properties:{},required:[]}}},
  {type:"function",function:{name:"list_dir",description:"列出目录下的文件和子目录",parameters:{type:"object",properties:{path:{type:"string",description:"目录路径"}},required:["path"]}}},
  {type:"function",function:{name:"read_file",description:"读取文本文件内容",parameters:{type:"object",properties:{path:{type:"string"}},required:["path"]}}},
  {type:"function",function:{name:"write_file",description:"写入文本文件（覆盖）",parameters:{type:"object",properties:{path:{type:"string"},content:{type:"string"}},required:["path","content"]}}},
  {type:"function",function:{name:"create_doc",description:"创建Word文档(.docx)（搜索资料+读取文件后，把整理好的内容生成正式文档）",parameters:{type:"object",properties:{path:{type:"string",description:"保存路径，如 D:\\报告.docx"},content:{type:"string",description:"文档正文内容"}},required:["path","content"]}}},
  {type:"function",function:{name:"create_excel",description:"创建Excel表格(.xlsx)。用表头数组+行数据数组生成表格文件，用户要求建Excel/表格/统计表/台账时用此工具",parameters:{type:"object",properties:{path:{type:"string",description:"保存路径，如 C:\\Users\\123\\Desktop\\统计.xlsx"},headers:{type:"array",description:"表头列表，如 [姓名,数量]"},rows:{type:"array",description:"数据行列表，每行一个数组，如 [[张三,5],[李四,8]]"},sheet_name:{type:"string",description:"工作表名称，默认Sheet1"}},required:["path","headers","rows"]}}},
  {type:"function",function:{name:"read_doc",description:"读取Word/Excel/PDF等文档内容（读取后可配合stat_data统计、create_doc生成报告）",parameters:{type:"object",properties:{path:{type:"string",description:"文档文件路径"}},required:["path"]}}},
  {type:"function",function:{name:"stat_data",description:"统计分析Excel/CSV数据（配合read_doc使用：先用read_doc读取文件，再用stat_data按列分组统计）",parameters:{type:"object",properties:{path:{type:"string",description:"Excel/CSV文件路径"},group_by:{type:"string",description:"按哪一列分组"},agg_col:{type:"string",description:"统计哪一列"},agg:{type:"string",description:"统计方式：sum求和/count计数/avg平均"}},required:["path"]}}},
  {type:"function",function:{name:"run_command",description:"执行系统命令。【重要】可执行Python脚本处理复杂数据（Excel统计/数据分析），示例：python -c \"import openpyxl; ...\"。危险操作会先征求同意",parameters:{type:"object",properties:{cmd:{type:"string"},timeout:{type:"number"}},required:["cmd"]}}},
  {type:"function",function:{name:"calculator",description:"数学计算",parameters:{type:"object",properties:{expr:{type:"string"}},required:["expr"]}}},
  {type:"function",function:{name:"file_copy",description:"复制文件",parameters:{type:"object",properties:{src:{type:"string"},dst:{type:"string"}},required:["src","dst"]}}},
  {type:"function",function:{name:"file_move",description:"移动/重命名文件",parameters:{type:"object",properties:{src:{type:"string"},dst:{type:"string"}},required:["src","dst"]}}},
  {type:"function",function:{name:"file_delete",description:"删除文件",parameters:{type:"object",properties:{path:{type:"string"}},required:["path"]}}},
  {type:"function",function:{name:"clipboard_get",description:"读取剪贴板内容",parameters:{type:"object",properties:{},required:[]}}},
  {type:"function",function:{name:"clipboard_set",description:"写入剪贴板",parameters:{type:"object",properties:{text:{type:"string"}},required:["text"]}}},
  {type:"function",function:{name:"screenshot",description:"截屏",parameters:{type:"object",properties:{},required:[]}}},
  {type:"function",function:{name:"ocr_image",description:"识别图片中的文字",parameters:{type:"object",properties:{path:{type:"string"}},required:["path"]}}},
  {type:"function",function:{name:"image_info",description:"获取图片信息",parameters:{type:"object",properties:{path:{type:"string"}},required:["path"]}}},
  {type:"function",function:{name:"system_info",description:"获取系统信息（CPU/内存/显卡/磁盘/常用路径如桌面文档下载等，排查问题或执行系统操作前先查状态，也用于确认桌面等路径）",parameters:{type:"object",properties:{},required:[]}}},
  {type:"function",function:{name:"save_memory",description:"保存一条长期记忆",parameters:{type:"object",properties:{text:{type:"string"}},required:["text"]}}},
  {type:"function",function:{name:"web_search",description:"联网搜索获取最新信息和事实（本地知识不足时必须先用），返回标题、链接和摘要",parameters:{type:"object",properties:{query:{type:"string",description:"搜索关键词，要简洁准确"},n:{type:"number",description:"返回结果数量，默认5"}},required:["query"]}}},
  {type:"function",function:{name:"fetch_url",description:"抓取指定网页的完整正文内容（搜索后需要深入阅读某个网页时用）",parameters:{type:"object",properties:{url:{type:"string",description:"要抓取的网页URL"}},required:["url"]}}},
  {type:"function",function:{name:"feishu_read_doc",description:"【飞书文档专用】读取飞书在线文档(docx)的纯文本内容。看到 feishu.cn/docx/ 或 larksuite.com/docx/ 链接时必须用此工具，从链接中提取 document_id，不要用 fetch_url 或 run_command",parameters:{type:"object",properties:{document_id:{type:"string",description:"飞书文档ID，从链接中获取，如 https://xxx.feishu.cn/docx/【document_id】"}},required:["document_id"]}}},
  {type:"function",function:{name:"feishu_list_tables",description:"列出飞书多维表格中的所有数据表",parameters:{type:"object",properties:{app_token:{type:"string",description:"多维表格app_token，从链接中获取，如 https://xxx.feishu.cn/base/【app_token】"}},required:["app_token"]}}},
  {type:"function",function:{name:"feishu_read_records",description:"读取飞书多维表格记录",parameters:{type:"object",properties:{app_token:{type:"string"},table_id:{type:"string",description:"数据表ID，可先用feishu_list_tables获取"},page_size:{type:"number",description:"每页条数，默认20"}},required:["app_token","table_id"]}}},
  {type:"function",function:{name:"feishu_search_records",description:"搜索飞书多维表格记录",parameters:{type:"object",properties:{app_token:{type:"string"},table_id:{type:"string"},filter:{type:"string",description:"筛选条件，格式：field=value;field2=value2（分号分隔多个条件）"},page_size:{type:"number"}},required:["app_token","table_id"]}}},
  {type:"function",function:{name:"feishu_create_record",description:"向飞书多维表格新增一条记录（需用户确认）",parameters:{type:"object",properties:{app_token:{type:"string"},table_id:{type:"string"},fields:{type:"object",description:"字段名和值的键值对"}},required:["app_token","table_id","fields"]}}},
  {type:"function",function:{name:"feishu_update_record",description:"更新飞书多维表格记录（需用户确认）",parameters:{type:"object",properties:{app_token:{type:"string"},table_id:{type:"string"},record_id:{type:"string"},fields:{type:"object"}},required:["app_token","table_id","record_id","fields"]}}},
];
const TOOL_NAMES = new Set(TOOLS.map(t => t.function.name));
const TOOL_RISK = { run_command:3, file_delete:3, file_move:2, file_copy:2, write_file:2, create_doc:2, create_excel:2, clipboard_set:2, feishu_create_record:2, feishu_update_record:2 };
/* 危险操作确认弹窗的人性化描述：标题 + 根据参数生成的描述 */
const TOOL_CONFIRM_LABELS = {
  run_command:       { title: "执行系统命令",   desc: a => "命令：" + ((a.cmd||"").substring(0,120) || "(空)") },
  file_delete:       { title: "删除文件",       desc: a => "路径：" + (a.path||a.file||"(未指定)") },
  file_move:         { title: "移动文件",       desc: a => (a.from||a.src||"?") + "  →  " + (a.to||a.dest||"?") },
  file_copy:         { title: "复制文件",       desc: a => (a.from||a.src||"?") + "  →  " + (a.to||a.dest||"?") },
  write_file:        { title: "写入文件",       desc: a => "路径：" + (a.path||a.file||"?") + "（" + ((a.content||"").length) + " 字符）" },
  create_doc:        { title: "创建文档",       desc: a => "标题：" + (a.title||a.name||a.filename||"(未命名)") },
  create_excel:      { title: "创建 Excel",     desc: a => "路径：" + (a.path||a.filename||a.name||"(未指定)") },
  clipboard_set:     { title: "写入剪贴板",     desc: a => "内容长度：" + ((a.text||a.content||"").length) + " 字符" },
  feishu_create_record:{ title:"飞书：创建记录", desc: a => "表：" + (a.app_token||a.table_id||"?") },
  feishu_update_record:{ title:"飞书：更新记录", desc: a => "记录：" + (a.record_id||"?") },
  browser_open:      { title: "浏览器：打开页面", desc: a => "URL：" + (a.url||"?") },
  browser_download:  { title: "浏览器：下载文件", desc: a => "URL：" + (a.url||"?") },
};
const RISK_LABEL = {1:"",2:"⚠️ 需确认",3:"🚫 高风险"};

/* ================= Store：单一数据源 ================= */
/* ========== 全局错误处理 ========== */
window.addEventListener('error', function(e) {
  console.error('全局错误:', e.message, e.filename, e.lineno);
  // 不阻断页面，只记录日志
});
window.addEventListener('unhandledrejection', function(e) {
  console.error('未处理的Promise拒绝:', e.reason);
});

/**
 * 全局状态管理器
 * 管理：会话列表、当前会话、任务状态、设置、记忆、token统计
 * 采用发布-订阅模式，状态变更时通知所有订阅者
 */
const store = {
  state: {
    convs: [], currentConvId: null,
    task: null,  // {convId, phase, step, abortCtrl}
    busy: false,
    settings: { mode:'agent', autoMemory:true, maxSteps:MAX_STEPS_DEFAULT, model:MODEL },
    memory: [],
    tokens: { session:0 },
    loadedFiles: [],
    pendingImg: null,
    genSpeed: 0, genTokens: 0, genStartTime: 0,  /* 实时生成速度 */
  },
  listeners: [],
  subscribe(fn) { this.listeners.push(fn); return () => { this.listeners = this.listeners.filter(f => f !== fn); }; },
  notify() { this.listeners.forEach(fn => fn(this.state)); },

  /* 会话 */
  addConv() {
    const c = { id:"c_"+Date.now()+"_"+Math.random().toString(36).slice(2,6), title:"新对话", messages:[], ts:Date.now() };
    this.state.convs.unshift(c);
    this.state.currentConvId = c.id;
    if (typeof clearSearchCache === "function") clearSearchCache();
    if (typeof clearLoadedFiles === "function") clearLoadedFiles();
    this.saveConvs(); this.notify(); return c;
  },
  /**
   * 切换当前会话
   * 重要：切换前必须中断正在执行的任务，避免后台继续运行
   * 同时清理流式输出状态，避免UI残留
   * @param {string} id - 目标会话ID
   */
  switchConv(id) {
    if (id === this.state.currentConvId) return;
    // 如果有任务正在执行，先中断任务（防止后台继续占用资源）
    if (this.state.task && this.state.task.abortCtrl) {
      try { this.state.task.abortCtrl.abort(); } catch(e) {}
    }
    this.state.task = null;
    this.state.busy = false;
    this._pendingInstructions = [];  // 切换会话清空待注入指令，防止跨会话串任务
    // 清理流式输出状态
    if (typeof ui !== "undefined") {
      ui._streamText = "";
      ui._streamPending = false;
      ui._streamLen = 0;
    }
    this.state.currentConvId = id;
    this.saveConvs();
    this.notify();
  },
  deleteConv(id) {
    if (this.state.convs.length <= 1) return;
    const idx = this.state.convs.findIndex(c => c.id === id);
    if (idx < 0) return;
    this.state.convs.splice(idx, 1);
    if (this.state.currentConvId === id) this.state.currentConvId = this.state.convs[0].id;
    this.saveConvs(); this.notify();
  },
  getCurrentConv() { return this.state.convs.find(c => c.id === this.state.currentConvId); },
  addMessage(convId, msg) {
    const c = this.state.convs.find(c => c.id === convId);
    if (!c) return;
    c.messages.push(msg); c.ts = Date.now();
    if (c.title === "新对话" && msg.role === "user") c.title = msg.content.slice(0,20) + (msg.content.length > 20 ? "…" : "");
    /* 用户消息时，把会话移到顶部 */
    if (msg.role === "user") {
      const idx = this.state.convs.indexOf(c);
      if (idx > 0) { this.state.convs.splice(idx, 1); this.state.convs.unshift(c); }
    }
    this.saveConvs();
  },

  /* 任务 */
  startTask(convId) {
    this.state.task = { convId, phase:"启动中", step:0, abortCtrl:new AbortController() };
    this.state.busy = true; this.notify();
  },
  updateTask(patch) { if (this.state.task) Object.assign(this.state.task, patch); },
  endTask() {
    if (this.state.task) {
      if (this.state.task.abortCtrl) {
        try { this.state.task.abortCtrl.abort(); } catch(e) {}
      }
      this.state.task = null;
    }
    this.state.busy = false;
    this._pendingInstructions = [];  // 任务结束清空待注入指令，避免跨任务/跨会话泄漏
    // 清理流式输出状态
    if (typeof ui !== "undefined") {
      ui._streamText = "";
      ui._streamPending = false;
      ui._streamLen = 0;
    }
    this.notify();
  },

  /* 持久化 */
  saveConvs() {
    try {
      localStorage.setItem("rui_convs", JSON.stringify(this.state.convs));
      localStorage.setItem("rui_cur", this.state.currentConvId);
    } catch(e) {
      console.warn("会话保存失败（可能是localStorage已满）：", e.message);
      // 尝试清理旧的工具调用结果数据，只保留最近的
      try {
        for (const conv of this.state.convs) {
          for (const msg of conv.messages) {
            if (msg._stepData && msg._stepData.length > 10) {
              msg._stepData = msg._stepData.slice(-10);
            }
          }
        }
        localStorage.setItem("rui_convs", JSON.stringify(this.state.convs));
        localStorage.setItem("rui_cur", this.state.currentConvId);
        console.log("已清理旧数据并重新保存成功");
      } catch(e2) {
        console.error("清理后仍保存失败：", e2.message);
      }
    }
  },
  loadConvs() {
    try {
      const c = localStorage.getItem("rui_convs");
      if (c) this.state.convs = JSON.parse(c);
      const cur = localStorage.getItem("rui_cur");
      if (cur && this.state.convs.find(c => c.id === cur)) this.state.currentConvId = cur;
    } catch(e) {}
    if (!this.state.convs.length) this.addConv();
    else if (!this.state.currentConvId) this.state.currentConvId = this.state.convs[0].id;
  },
  saveSettings() { try { localStorage.setItem("rui_settings", JSON.stringify(this.state.settings)); } catch(e) {} },
  loadSettings() { try { const s = localStorage.getItem("rui_settings"); if (s) { const parsed = JSON.parse(s); Object.assign(this.state.settings, parsed); if (parsed.agent !== undefined && parsed.mode === undefined) { this.state.settings.mode = parsed.agent ? "agent" : "normal"; } } } catch(e) {} },
  saveMemory() { try { localStorage.setItem("rui_memory", JSON.stringify(this.state.memory)); } catch(e) {} },
  loadMemory() { try { const m = localStorage.getItem("rui_memory"); if (m) this.state.memory = JSON.parse(m); } catch(e) {} },
};

/* ================= 工具层 ================= */
/* 前端搜索缓存：会话级别，5分钟TTL + 100条上限，防时效性查询返回旧数据、防内存膨胀 */
const SEARCH_CACHE_TTL = 5 * 60 * 1000;
const SEARCH_CACHE_MAX = 100;
const searchCache = new Map();
function clearSearchCache() { searchCache.clear(); }
/* 新建会话时清空已加载文件（每个会话独立的文件上下文） */
function clearLoadedFiles() { if (store.state.loadedFiles) store.state.loadedFiles = []; const fi = document.getElementById("fileinfo"); if (fi) fi.classList.remove("show"); }

const toolLayer = {
  async exec(name, args, abortSignal) {
    if (!TOOL_NAMES.has(name)) return { ok:false, error:"未知工具: "+name };
    /* save_memory 本地闭环：直接写入长期记忆（localStorage），无需后端实现 */
    if (name === "save_memory") {
      const _t = (args && args.text ? String(args.text) : "").trim();
      if (_t) { if (!store.state.memory.includes(_t)) { store.state.memory.push(_t); store.saveMemory(); } return { ok:true, saved:true }; }
      return { ok:false, error:"记忆内容为空" };
    }
    /* web_search 前端缓存：同一会话内相同关键词直接返回缓存 */
    if (name === "web_search" && args && args.query) {
      const cacheKey = String(args.query).trim().toLowerCase();
      if (searchCache.has(cacheKey)) {
        const cached = searchCache.get(cacheKey);
        /* TTL过期则删除并重新搜索；未过期返回缓存数据 */
        if (Date.now() - (cached._ts || 0) >= SEARCH_CACHE_TTL) {
          searchCache.delete(cacheKey);
        } else {
          return Object.assign({}, cached.data, { _cached: true, _cacheNote: "（复用本会话之前的搜索结果）" });
        }
      }
    }
    try {
      const r = await fetch(AGENT_API+"/api/exec", { method:"POST", headers:{"Content-Type":"application/json", "X-Access-Token": ACCESS_TOKEN}, body:JSON.stringify({tool:name, params:args||{}}), signal:abortSignal });
      const result = await r.json();
      /* 后端需要确认时：自动弹窗确认后带 confirmed 重发一次 */
      if (result && result.need_confirm) {
        const ok2 = await ui.confirmAction(result.tool || name, result.params || args || {});
        if (!ok2) return { ok:false, error:"用户拒绝执行" };
        return await this.exec(name, Object.assign({}, args, result.params || {}, {confirmed:true}), abortSignal);
      }
      /* web_search 结果存入缓存 */
      if (name === "web_search" && args && args.query && result && result.results) {
        const cacheKey = String(args.query).trim().toLowerCase();
        searchCache.set(cacheKey, { _ts: Date.now(), data: result });
        /* 超过上限则淘汰最旧条目（Map按插入顺序，第一个最旧） */
        if (searchCache.size > SEARCH_CACHE_MAX) {
          const oldest = searchCache.keys().next().value;
          if (oldest !== undefined) searchCache.delete(oldest);
        }
      }
      return result;
    } catch(e) { return { ok:false, error:String(e.message||e) }; }
  },
  riskOf(name) { return TOOL_RISK[name] || 1; },
};

/* ================= 流式对话（双超时保护） ================= */
/**
 * 调用llama.cpp流式API，支持思考过程和工具调用
 * @param {Object} body - 请求体 {model, messages, tools, max_tokens, stream_options, chat_template_kwargs}
 * @param {Object} callbacks - 回调函数 {onToken, onReasoning, onToolCall}
 * @returns {Object} 输出结果 {content, reasoning, toolCalls, finish, usage, timings}
 */
async function chatStream(body, callbacks) {
  /* SSE断线重连：最多尝试2次（首次+1次重试）；网络错误/5xx自动重试，4xx/用户中止不重试；读取中途断开返回部分数据 */
  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const timeoutCtrl = new AbortController();
    const timeoutId = setTimeout(() => timeoutCtrl.abort(), 300000);
    const signals = [timeoutCtrl.signal];
    if (store.state.task && store.state.task.abortCtrl) signals.push(store.state.task.abortCtrl.signal);
    const combined = typeof AbortSignal.any === "function" ? AbortSignal.any(signals) : timeoutCtrl.signal;
    try {
      const resp = await fetch("/v1/chat/completions", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(Object.assign({stream:true}, body)), signal:combined });
      clearTimeout(timeoutId);
      if (!resp.ok) {
        const err = await resp.text();
        const errObj = new Error("HTTP "+resp.status+(err?"："+err.slice(0,200):""));
        if (resp.status < 500) throw errObj;  /* 4xx不重试 */
        throw errObj;  /* 5xx可重试 */
      }
      const reader = resp.body.getReader();
      const dec = new TextDecoder("utf-8");
      let buf = "";
      const out = { content:"", reasoning:"", toolCalls:null, finish:null, usage:null, timings:null };
      while (true) {
        const readPromise = reader.read();
        let readTimer;
        const readTimeout = new Promise((_,rej) => { readTimer = setTimeout(() => rej(new Error("模型响应超时（120秒无新数据）")), 120000); });
        let done, value;
        try { const r = await Promise.race([readPromise, readTimeout]); done = r.done; value = r.value; }
        catch (readErr) {
          clearTimeout(readTimer);
          /* 读取中途断开：如果已收到部分数据，返回部分结果并标记中断 */
          if (out.content || out.reasoning || (out.toolCalls && out.toolCalls.length)) {
            out.finish = out.finish || "interrupted";
            return out;
          }
          throw readErr;  /* 没收到任何数据，抛错走重试 */
        }
        finally { clearTimeout(readTimer); }
        if (done) break;
        buf += dec.decode(value, {stream:true});
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim(); buf = buf.slice(nl+1);
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") return out;
          try {
            const j = JSON.parse(payload);
            if (j.usage) out.usage = j.usage;
            if (j.timings) out.timings = j.timings;
            const ch = j.choices && j.choices[0]; if (!ch) continue;
            const delta = ch.delta || {};
            if (delta.reasoning_content) { out.reasoning += delta.reasoning_content; callbacks && callbacks.onReasoning && callbacks.onReasoning(out.reasoning); }
            if (delta.content) { out.content += delta.content; callbacks && callbacks.onToken && callbacks.onToken(out.content); }
            if (delta.tool_calls) {
              out.toolCalls = out.toolCalls || [];
              for (const t of delta.tool_calls) {
                const i = t.index || 0;
                out.toolCalls[i] = out.toolCalls[i] || { id:"", type:"function", function:{ name:"", arguments:"" } };
                if (t.id) out.toolCalls[i].id += t.id;
                if (t.function && t.function.name) out.toolCalls[i].function.name += t.function.name;
                if (t.function && t.function.arguments) out.toolCalls[i].function.arguments += t.function.arguments;
              }
            }
            if (ch.finish_reason) out.finish = ch.finish_reason;
          } catch(e) {}
        }
      }
      return out;
    } catch (e) {
      clearTimeout(timeoutId);
      lastError = e;
      /* 用户主动中止不重试 */
      if (e.name === "AbortError") throw e;
      /* 4xx不重试 */
      if (e.message && /^HTTP 4\d\d/.test(e.message)) throw e;
      /* 最后一次尝试不重试 */
      if (attempt === 1) throw e;
      /* 等待1.5秒后重试 */
      await new Promise(r => setTimeout(r, 1500));
    } finally {
      clearTimeout(timeoutId);
    }
  }
  throw lastError;
}

/* ================= Agent Engine：ReAct 循环 ================= */
/* 反思器：任务卡住/失败时，让模型基于已有轨迹总结原因并给出替代回答 */
async function reflectAndAnswer(liveMsg, msgs, reason, store, ui, MODEL, chatStream, abortSignal) {
  try {
    store.updateTask({ phase:"反思中-"+reason, step:(store.state.task && store.state.task.step) || 0 });
    ui.updateStatusOnly();
    const stepInfo = (liveMsg._stepData || []).map(sd => sd.tool + "(" + JSON.stringify(sd.args).substring(0, 80) + ")").join("、");
    const thinkInfo = (liveMsg._think || "").substring(0, 500);
    const body = { model:MODEL, messages:[
      {role:"system", content:"你是反思器。任务执行遇到问题（" + reason + "）。基于已有的思考和工具调用记录，输出一段给用户的收尾回答：1. 说明已获取到什么信息 2. 说明卡在哪里 3. 给出1-2个可行的替代建议（换搜索词/换方法/让用户补充信息）。直接输出回答正文，不要输出思考过程，不要超过150字。"},
      {role:"user", content:"思考记录：" + thinkInfo + "\n已调用工具：" + (stepInfo || "无")}
    ], max_tokens:300, chat_template_kwargs:{ enable_thinking:false } };
    const rOut = { content:"" };
    try {
      await chatStream(body, { onToken: (c) => { rOut.content = c; }, onReasoning: () => {} });
    } catch(e) {}
    if (rOut.content && rOut.content.trim().length > 10) {
      liveMsg.content = rOut.content.trim();
      liveMsg._reflect = reason;
    }
  } catch(e) {}
}

const agentEngine = {
  buildSystemPrompt() {
    let sys = `你是 Rui AI，运行在用户本地电脑上的智能助手，可调用工具完成任务。

【核心定位】
你是本地9B模型，知识有限且不包含最新信息。涉及事实性问题、最新资讯、专业知识时，必须先 web_search 搜索，绝对不要凭记忆编造。简单问题（问候/闲聊/常识）直接回答，不调用工具。

【问题判断】（按分类决定是否搜索）
- 直接回答（不搜索）：问候闲聊、基础常识（植物养护/生活经验）、有歧义但属常识范畴（如"绿龙和老鼠谁厉害"可能是CS2战队也可能是奇幻生物→直接给两种答案）
- 必须搜索：事实数据（比赛结果/新闻/人物信息）、具体成分（毒性/营养成分）、最新资讯、专业领域（医学/法律/技术）、对比分析（实力对比/产品对比）
- 搜索+免责：医学诊断、法律条款、投资建议
- 搜索2-3次还找不到就基于已有知识给出答案，明确标注"基于已有知识，无法确认最新信息"，不要无限搜索

【搜索策略】
- 关键词优化：去掉"吗/呢/怎么/什么"等疑问词，加领域限定词（如"CS2 战队"、"盆栽 养护"），用引号精确匹配专有名词
- 拆解搜索：复杂问题拆成多个关键词分别搜索，先搜实体确认是什么，再搜对比数据
- 来源优先级：官方网站/百科 > 权威媒体 > 知乎高赞/B站高播放 > 普通新闻 > 不明来源
- 交叉验证：多个来源一致才确认，来源冲突时明确说明"信息有冲突"
- 时效性标注：回答时标注"根据搜索结果"、"根据XX来源"，不编造来源
- 失败处理：第一次搜索结果不理想，调整关键词再搜（换同义词/加限定词/去疑问词），最多3种组合；仍失败则基于已有知识回答并说明"搜索未找到权威信息"

【回答要求】
- 最终回答是给用户看的成品，必须干净、完整、可直接阅读。不要包含任何思考过程、分析推理、过程性语句或收尾语句
- 先给结论，再展开论述，不要铺垫半天还没说重点
- 对于性健康、两性关系、生理知识、成人健康咨询等成人相关话题，应以科学、客观、健康的态度回答，提供准确的知识和建议，不要回避或过度敏感。涉及健康问题时建议咨询专业医生
- 对比类问题用表格对比，最后给明确结论（谁更厉害/哪个更好）
- 步骤类问题用编号分点，每步简洁明确
- 分析类问题先给结论，再分点论述原因/影响/建议
- 关键信息加粗，不确定的信息明确标注"推测"或"无法确认"
- 简单问题简短回答，复杂问题结构化回答，不要所有问题都长篇大论
- 【严格按用户指定步骤执行】如果用户明确列出了第1步、第2步...第N步，必须严格按顺序执行，不要自己增加或跳过步骤。每完成一步必须把该步的结果（数据、统计、表格、分析）写入最终回答区域，不能只放在思考过程里
- 【任务完成判断】只有当用户要求的所有步骤都完成且结果都写入最终回答后，才能结束任务。如果还有未完成的步骤，必须继续调用工具执行，不能提前输出最终回答
- 【工具调用失败处理】工具调用失败后，重试1次；如果仍然失败，换一种方式实现（如用不同工具或参数），不要因为一个工具失败就放弃整个任务
- 【思考与回答的分工】思考过程只用于规划、推理、判断是否需要工具。所有的分析结果、统计数据、表格、结论必须放在最终回答区域，用户只能看到最终回答，看不到思考过程

【思考与回答的边界】（最重要）
- 你有两个输出区域：思考过程 和 最终回答，两者必须严格分开
- 思考过程：用来分析问题、规划步骤、判断是否需要工具、复盘结果。可以自由表达，不需要固定格式
- 最终回答：给用户看的最终结果，必须是干净、完整、可直接阅读的内容
- 【绝对禁止】把思考过程的内容（包括"我正在分析""让我思考一下""首先需要""总结"等过程性语句，以及任何分析推理过程）写进最终回答里
- 【绝对禁止】在最终回答末尾添加"任务已完成""以上是我的分析"等收尾语句
- 思考要简洁，抓住核心，不要长篇大论，不要重复用户问题
- 不需要搜索时直接回答，不要为了用工具而用工具
- 有歧义时在思考中说明，最终回答直接给出结论或分情况回答

【工具调用规范】
- 只显示工具名称和关键参数，不显示完整参数和原始输出
- 工具失败时自动重试（最多3次，每次用不同参数/关键词），仍失败则换替代工具，如实告知
- 搜索失败时先调整关键词重试（去疑问词/换同义词/加限定词），不要直接放弃
- 危险操作（删除文件/修改系统）先确认，用户确认后直接执行
- 飞书文档链接用 feishu_read_doc，多维表格用 feishu_list_tables/feishu_read_records

【代码优先原则】（最重要）
- 对于复杂的数据处理任务（Excel统计、数据分析、报告生成、批量处理），直接生成完整的Python脚本，用 run_command 执行，不要一步一步调用 read_doc、stat_data 等工具
- 【脚本编写要点】
  1. 文件路径用原始字符串 r"路径" 或双反斜杠 "D:\\llama\\uploads\\文件.xlsx"，避免转义错误
  2. 用 openpyxl.load_workbook(path, read_only=True) 读取大文件，data_only=True获取计算值
  3. 统计时先打印列名和前2行数据确认结构，再做筛选统计
  4. 筛选字符串用 '关键词' in str(cell.value)，注意None值判断
  5. 结果用print输出，包含统计数字和简要说明
- 【推荐脚本模板】
  import openpyxl
  wb = openpyxl.load_workbook(r"文件路径", read_only=True, data_only=True)
  ws = wb.active
  rows = list(ws.iter_rows(values_only=True))
  headers = rows[0]
  print("列名:", headers)
  print("总行数:", len(rows)-1)
  # 筛选统计
  target_col = headers.index("专项名称")
  count = sum(1 for r in rows[1:] if r[target_col] and "新款理想MEGA" in str(r[target_col]))
  print("新款理想MEGA数据条数:", count)
- 执行命令示例：python -c "完整脚本" 或 先 write_file 保存脚本再 python script.py 执行
- 简单任务（读取单个文件、搜索信息）可以直接用对应工具，但复杂任务必须代码优先
- 生成脚本前先在思考中说明脚本要做什么，然后立即调用 run_command 执行，不要反复讨论工具用法

【可用工具列表】
- web_search(q)：联网搜索，返回标题/链接/摘要
- browser_open(url)：用真实浏览器打开网页，支持JS渲染和动态内容
- browser_click(selector)：点击页面元素（CSS选择器）
- browser_type(selector, text)：在输入框中输入文字
- browser_press(key)：按键（如 Enter、Escape）
- browser_get_text(selector?)：获取页面文本（可选指定元素）
- browser_get_html(selector?)：获取页面HTML（可选指定元素）
- browser_wait(selector)：等待元素出现
- browser_scroll(direction, amount)：滚动页面
- browser_evaluate(script)：在页面执行JavaScript代码
- browser_screenshot(path?)：截图保存
- browser_download(url, save_path?)：下载文件到本地
- browser_back/forward/reload/close：浏览器导航和关闭
- read_file(path)：读取本地文本文件
- read_doc(path)：读取Word/Excel/PDF等文档
- stat_data(params)：统计分析Excel/CSV数据
- create_doc(path, content)：创建文档
- create_excel(path, headers, rows)：创建Excel表格
- list_dir(path)：列出目录内容
- run_command(cmd)：执行系统命令。【重要】可用于执行Python脚本处理复杂数据，示例：python -c "import openpyxl; wb=openpyxl.load_workbook('文件路径'); ..."
- system_info()：获取系统信息
- feishu_read_doc(url)：读取飞书文档
- feishu_list_tables(app_token)：列出飞书多维表格
- feishu_read_records(app_token, table_id)：读取飞书表格记录

【常见实体昵称参考】
- CS2战队：绿龙=Team Spirit、老鼠=MOUZ、NAVI=Natus Vincere、A队=Astralis、Faze=FaZe Clan、G2=G2 Esports、小蜜蜂=Vitality、黑豹=FURIA、C9=Cloud9、VP=Virtus.pro
- 其他：苹果=Apple、谷歌=Google、微软=Microsoft、特斯拉=Tesla、比亚迪=BYD、理想=Li Auto
- 遇到不在列表中的实体，直接搜索实体名称确认是什么

【禁止行为】
- 绝对不要在思考中反复讨论工具用法超过2次，想清楚就立即调用工具或生成代码执行
- 绝对不要不搜索就回答事实性/对比性/分析性问题
- 绝对不要同一个关键词反复搜索超过2次
- 绝对不要搜索/调用工具超过6次还不给出回答
- 绝对不要凭记忆编造不确定的信息
- 绝对不要陷入重复循环（相同思考/相同工具调用连续2次立即停止）
- 绝对不要在用户指出错误后不重新查证就坚持原答案

【核心原则】
1. 先搜索再回答，不编造不确定的信息
2. 工具返回结果后基于真实结果回答，用户指出错误时立即重新查证
3. 同一会话中已搜索过的信息/已读取的文件，直接复用，不要重复搜索
4. 回答事实性问题时标注来源，如（来源：百度百科/知乎）`;
    if (store.state.settings.autoMemory && store.state.memory.length) {
      sys += "\n\n【用户长期记忆】\n" + store.state.memory.map((m,i) => (i+1)+". "+m).join("\n");
    }
    /* 已上传文件：文本文件直接注入内容，二进制文件提示用 read_doc 工具读取 */
    if (store.state.loadedFiles && store.state.loadedFiles.length) {
      const textFiles = store.state.loadedFiles.filter(f => f.content);
      const binFiles = store.state.loadedFiles.filter(f => f.path && f.needTool);
      if (textFiles.length) {
        sys += "\n\n【已上传文本文件】\n" + textFiles.map(f => "文件: " + f.name + "\n内容:\n" + f.content.substring(0, 8000)).join("\n\n---\n\n");
      }
      if (binFiles.length) {
        sys += "\n\n【已上传文件 - 必须立即调用 read_doc 工具读取】\n" + binFiles.map(f => "文件: " + f.name + "\n路径: " + f.path).join("\n\n") + "\n\n重要：你必须在第一步就调用 read_doc 工具（参数 path 填上面的完整路径）来读取文件内容，绝对不能跳过工具直接回答，也不能假装已经读取了文件。读取完成后再基于真实内容回答用户。";
      }
    }
    return sys;
  },

  /* AI 助手模式：ReAct 循环 */
  /**
   * Agent模式主执行循环：思考 -> 工具调用 -> 观察 -> 再思考
   * 工作流程：
   * 1. 构建系统提示词和消息列表
   * 2. 调用模型进行思考和决策
   * 3. 解析工具调用并执行
   * 4. 将工具结果反馈给模型
   * 5. 循环直到任务完成或达到最大步数
   * @param {string} userText - 用户输入文本
   * @param {string} convId - 会话ID
   * @returns {string} 最终回答内容
   */
  async run(userText, convId) {
    const conv = store.state.convs.find(c => c.id === convId);
    if (!conv) return "";
    store.startTask(convId);
    const abortSignal = store.state.task.abortCtrl.signal;
    const sysPrompt = this.buildSystemPrompt();
    const msgs = [{role:"system", content:sysPrompt}, ...conv.messages.map(m => ({role:m.role, content:m.content})), {role:"user", content:userText}];
    store.addMessage(convId, {role:"user", content:userText, _mode:"agent"});
    let liveMsg = { role:"assistant", content:"", _stepData:[], _think:"", _mode:"agent" };
    store.addMessage(convId, liveMsg);
    const isAgent = true;  // Agent模式始终启用思考过程
    store.notify();

    let totalPrompt = 0, totalComp = 0, stepCount = 0;
    store.state.genSpeed = 0; store.state.genTokens = 0; store.state.genStartTime = 0;
    const maxSteps = store.state.settings.maxSteps || MAX_STEPS_DEFAULT;
    store._verified = false;  /* 每个任务独立验证 */
    const readFiles = new Set();
    /* 强化防循环机制：多维度检测 */
    let lastThinkSnippet = "";
    let repeatThinkCount = 0;
    let lastToolCall = "";
    let repeatToolCount = 0;
    const toolCallHistory = [];
    const toolResultHashes = new Set();
    let noProgressCount = 0;
    let thinkOnlyCount = 0;
    let searchCount = 0;  // 搜索次数计数器
    let searchLimitReached = false;  // 是否已达到搜索上限
    const REPEAT_THRESHOLD = 2;
    const NO_PROGRESS_THRESHOLD = 3;
    const THINK_ONLY_THRESHOLD = 3;
    const MAX_SEARCH_COUNT = 6;  // 同一个任务最多搜索6次

    function stringSimilarity(s1, s2) {
      if (!s1 || !s2) return 0;
      const longer = s1.length > s2.length ? s1 : s2;
      const shorter = s1.length > s2.length ? s2 : s1;
      if (longer.length === 0) return 1.0;
      let matches = 0;
      for (let i = 0; i < shorter.length; i++) { if (longer.includes(shorter[i])) matches++; }
      return matches / longer.length;
    }
    function normalizeToolCall(name, args) {
      try {
        const sorted = {};
        Object.keys(args).sort().forEach(k => { sorted[k] = args[k]; });
        return name + ":" + JSON.stringify(sorted).replace(/\s+/g, "");
      } catch(e) { return name + ":" + String(args); }
    }
    function detectLoopPattern() {
      if (toolCallHistory.length < 4) return false;
      const len = toolCallHistory.length;
      if (len >= 4 && toolCallHistory[len-1] === toolCallHistory[len-3] && toolCallHistory[len-2] === toolCallHistory[len-4]) return true;
      if (len >= 6 && toolCallHistory[len-1] === toolCallHistory[len-4] && toolCallHistory[len-2] === toolCallHistory[len-5] && toolCallHistory[len-3] === toolCallHistory[len-6]) return true;
      return false;
    }

    try {
      for (let step = 0; step < maxSteps; step++) {
        if (abortSignal.aborted) throw new Error("aborted");
        stepCount++;
        store.updateTask({ step:stepCount, phase:"思考中" });
        ui.updateStatusOnly();

        /* 新指令注入：任务执行中用户发的新消息 → 结束当前回答气泡，在新需求下面创建新气泡继续回答 */
        while (store._pendingInstructions && store._pendingInstructions.length) {
          const ins = store._pendingInstructions.shift();
          store.updateTask({ phase:"重新规划中", step:stepCount });
          ui.updateStatusOnly();
          /* 结束当前回答气泡：给一个自然的收尾过渡，不要戛然而止 */
          if (liveMsg) {
            if (liveMsg.content && liveMsg.content.trim()) {
              /* 先过滤掉思考阶段标题（模型可能把思考过程输出到了content里） */
              let filteredContent = liveMsg.content
                .replace(/【解析输入】[\s\S]*?(?=【信息调取】|【任务规划】|【分析推理】|【总结回答】|$)/g, '')
                .replace(/【信息调取】[\s\S]*?(?=【分析推理】|【总结回答】|$)/g, '')
                .replace(/【分析推理】[\s\S]*?(?=【总结回答】|$)/g, '')
                .replace(/【总结回答】/g, '')
                .replace(/【任务规划】[\s\S]*?(?=【|$)/g, '')
                .replace(/【调整计划】[\s\S]*?(?=【|$)/g, '')
                .trim();
              /* 如果过滤后还有实质内容，在末尾加收尾说明；如果过滤后为空，用占位说明 */
              if (filteredContent && filteredContent.length > 5) {
                if (!filteredContent.endsWith("…") && !filteredContent.endsWith("...")) {
                  liveMsg.content = filteredContent + "\n\n（收到你的新需求，我先暂停当前分析，结合新需求一起重新规划…）";
                } else {
                  liveMsg.content = filteredContent;
                }
              } else {
                liveMsg.content = "（已接收新需求，正在重新规划…）";
              }
            } else {
              /* 还没有回答内容，给占位说明 */
              liveMsg.content = "（已接收新需求，正在重新规划…）";
            }
          }
          /* 在新需求下面创建新的 assistant 气泡，后续思考和回答都更新在这里 */
          liveMsg = { role:"assistant", content:"", _stepData:[], _think:"", _mode:"agent" };
          store.addMessage(convId, liveMsg);
          ui.renderMessages();  /* 立即渲染，确保新气泡出现在页面上（store.notify是空操作） */
          /* 模型上下文：把重规划引导合并到用户新需求里（作为一条user message，不破坏messages结构，避免system message不在开头导致llama.cpp报500） */
          msgs.push({role:"user", content: ins + "\n\n【任务执行中插入新需求 - 请立即重规划】\n0.【原始目标不变·最高优先级】用户最初的任务仍然必须完整完成；本条新需求只是在原任务基础上的追加或补充，不是替换。最终回答必须同时覆盖原始任务的全部要求和本条新需求，不能只回答新需求、不能遗漏原始任务，也不要因此反问用户或中止原任务。\n1.【意图判断】这个新需求属于：新增子任务/修改已有任务/替换输出要求/调整优先级/补充信息\n2.【影响分析】与当前任务的关系：可并行执行/需先完成当前步骤/会推翻已完成部分/仅补充信息\n3.【复用已有成果】已完成的工具调用、已读取的文件、已搜索的结果直接复用，不要重复执行\n4.【重新规划】在思考中输出【调整计划】，列出更新后的后续步骤\n5.【冲突说明】如果新需求与已完成的不可逆操作冲突，明确说明\n6.然后继续执行更新后的计划，给出最终回答"});
        }

        /* 上下文压缩：长任务执行到一定步数后，压缩旧对话历史，明确列出已完成步骤，避免模型重复执行 */
        if (stepCount > 5) {
          const totalChars = msgs.reduce((sum, m) => sum + (m.content ? m.content.length : 0), 0);
          if (totalChars > 15000) {
            const firstUserIdx = msgs.findIndex(m => m.role === "user");
            const keepEnd = 5;
            if (msgs.length > firstUserIdx + keepEnd + 3) {
              /* 从中间消息中提取已完成步骤和关键结果 */
              const completedSteps = [];
              const keyResults = [];
              for (let i = firstUserIdx + 1; i < msgs.length - keepEnd; i++) {
                const m = msgs[i];
                if (m.role === "assistant" && m.content) {
                  /* 提取已完成步骤 */
                  const stepMatches = m.content.match(/第\s*(\d+)\s*步[^。\n]{0,30}(完成|已完成)/g);
                  if (stepMatches) completedSteps.push(...stepMatches);
                  /* 提取关键数据 */
                  const nums = m.content.match(/\d+[条%个小时]?/g);
                  if (nums && nums.length > 0) keyResults.push("数据: " + nums.slice(0,5).join(", "));
                }
                if (m.role === "assistant" && m._think) {
                  const thinkSteps = m._think.match(/第\s*(\d+)\s*步[^。\n]{0,30}(完成|已完成)/g);
                  if (thinkSteps) completedSteps.push(...thinkSteps);
                }
              }
              /* 构建清晰的摘要，明确告诉模型哪些已完成，哪些未完成 */
              const uniqueSteps = [...new Set(completedSteps)].slice(0, 8);
              const summary = "\n\n【上下文压缩 - 执行进度摘要】\n" +
                "【重要】以下步骤已完成，不要重复执行：\n" +
                (uniqueSteps.length > 0 ? uniqueSteps.join("\n") : "（前几步工具调用已执行，结果已用于分析）") + "\n\n" +
                "已获取的关键数据：\n" +
                (keyResults.length > 0 ? [...new Set(keyResults)].slice(0,5).join("\n") : "（数据已在之前步骤中处理）") + "\n\n" +
                "【指令】请从尚未完成的步骤继续执行，不要重新开始，不要重复读取已读取的文件。所有8步完成后再给最终回答。";
              /* 把摘要合并到第一条 system message 中 */
              if (msgs[0] && msgs[0].role === "system") {
                msgs[0].content += summary;
              }
              /* 删除中间消息，只保留 system + 第一条user + 最后5条 */
              msgs.splice(firstUserIdx + 1, msgs.length - keepEnd - firstUserIdx - 1);
            }
          }
        }

        /* 思考 + 决策 */
        const body = { model:MODEL, messages:msgs, tools:TOOLS, max_tokens:8192, stream_options:{include_usage:true}, chat_template_kwargs:{ enable_thinking:currentModelThinking } };
        // 会话切换检查：如果当前会话不是任务所属会话，跳过本次调用
        if (store.state.currentConvId !== convId) {
          console.log("会话已切换，跳过chatStream调用");
          break;
        }
        const st = await chatStream(body, {
          onReasoning: (r) => {
            // 会话切换检查：如果当前会话不是任务所属会话，不更新UI
            if (store.state.currentConvId !== convId) return;
            // 保存思考过程到liveMsg（关键：确保思考过程被持久化）
            liveMsg._think = r;
            // 流式更新UI上的思考过程显示
            ui.streamThink(r);
          },
          onToken: (c) => {
            // 会话切换检查：如果当前会话不是任务所属会话，不更新UI
            if (store.state.currentConvId !== convId) return;
            liveMsg.content = typeof c === "string" ? c : String(c || ""); ui.streamUpdate(liveMsg.content); ui.updateStatusOnly();
            if (!store.state.genStartTime) { store.state.genStartTime = Date.now(); store.state.genTokens = 0; }
            store.state.genTokens++;
            const elapsed = (Date.now() - store.state.genStartTime) / 1000;
            if (elapsed > 0.5) { store.state.genSpeed = store.state.genTokens / elapsed; ui.updateStatusOnly(); }
          },
        });
        if (st.usage) { totalPrompt += st.usage.prompt_tokens || 0; totalComp += st.usage.completion_tokens || 0; }
        const finish = st.finish;
        const toolCalls = st.toolCalls;

        /* length截断检测：思考用完token导致没有回答/工具调用时，自动补一次调用（最多2次） */
        if (finish === "length" && !liveMsg.content.trim() && (!toolCalls || !toolCalls.length)) {
          lengthRetryCount = (lengthRetryCount || 0) + 1;
          if (lengthRetryCount <= 2) {
            store.updateTask({ phase:"补全回答中(token截断)", step:stepCount });
            ui.updateStatusOnly();
            msgs.push({role:"assistant", content:st.content || ""});
            msgs.push({role:"user", content:"你刚才的思考被token长度截断了，没有给出最终回答或工具调用。请基于已有的思考和数据，直接给出最终回答（如果需要调用工具就调用工具），不要再重复长篇思考。"});
            continue;
          }
        }

        /* 思考内容重复检测（语义相似度 > 0.85 就算重复） */
        const thinkSnippet = (liveMsg._think || "").substring(0, 200).replace(/\s+/g, " ").trim();
        if (thinkSnippet && lastThinkSnippet) {
          const sim = stringSimilarity(thinkSnippet, lastThinkSnippet);
          if (sim > 0.85) {
            repeatThinkCount++;
            if (repeatThinkCount >= REPEAT_THRESHOLD) {
              await reflectAndAnswer(liveMsg, msgs, "思考过程重复", store, ui, MODEL, chatStream, abortSignal);
              if (!liveMsg.content) liveMsg.content = "（检测到思考过程重复，已自动停止。这个问题我暂时找不到答案，你可以换个问法或补充更多信息。）";
              store.updateTask({ phase:"停止-重复循环", step:stepCount });
              store.notify();
              return "";
            }
          } else {
            repeatThinkCount = 0;
          }
        } else {
          repeatThinkCount = 0;
        }
        lastThinkSnippet = thinkSnippet;

        /* 纯文本回答（无工具调用）分支 */
        if (finish !== "tool_calls") {
          /* 过程性内容拦截：多步任务已调过工具后，模型若把【阶段分析】/未完成的中间过程写进 content，
             不能当成最终答案提前结束——催它直接产出成品（受 THINK_ONLY_THRESHOLD 上限保护，不会死循环） */
          const rawContent = (st.content || "").trim();
          const usedAnyTool = (liveMsg._stepData || []).length > 0;
          const realContent = rawContent
            .replace(/\*\*(?:搜索完成|统计结果|执行结果|文件已读取|文档已创建)[\s\S]*$/g, "")
            .replace(/【[^】]*】[\s\S]*$/g, "").trim();
          const looksLikeProcess = /^\s*【/.test(rawContent)
            || /需要补充|继续搜索|待获取|尚未获取|让我(?:再|继续|先|进一步)|还需要(?:搜索|查询|调用)|下一步(?:该|要|会)/.test(rawContent)
            || (usedAnyTool && realContent.length < 40);
          if (usedAnyTool && looksLikeProcess && thinkOnlyCount < THINK_ONLY_THRESHOLD) {
            thinkOnlyCount++;
            msgs.push({role:"assistant", content:st.content || ""});
            msgs.push({role:"user", content:"你刚才输出的是中间分析过程，不是给用户的最终答案。请直接基于已经获取的全部数据，在最终回答区域写出完整成品（结论/要点/数据），不要再输出【】阶段标题或“搜索完成/执行结果”之类内部进度；如果确实还需调用工具就调用工具。"});
            store.updateTask({ phase:"整理最终回答中", step:stepCount });
            ui.updateStatusOnly();
            continue;
          }
          thinkOnlyCount++;
          if (thinkOnlyCount >= THINK_ONLY_THRESHOLD) {
            /* 检查是否已有足够的回答内容 */
            const hasEnoughAnswer = liveMsg.content && liveMsg.content.trim().length > 200;
            if (hasEnoughAnswer) {
              /* 已有足够回答，正常结束 */
              store.updateTask({ phase:"完成", step:stepCount });
              store.notify();
              return liveMsg.content;
            }
            /* 回答内容不足，提示模型继续执行，不停止 */
            thinkOnlyCount = 0;
            msgs.push({role:"assistant", content:st.content || ""});
            msgs.push({role:"user", content:"【重要提醒】你刚才的思考没有转化为最终回答或工具调用。请：1）如果还有未完成的步骤，立即调用相应工具继续执行；2）如果已有分析结果，立即把结果（数据、统计、表格、结论）写入最终回答区域；3）不要只在思考中分析而不输出结果。继续执行任务。"});
            store.updateTask({ phase:"继续执行中", step:stepCount });
            ui.updateStatusOnly();
            continue;
          }
        } else {
          thinkOnlyCount = 0;
        }

        /* 如果是工具调用 */
        if (finish === "tool_calls" && toolCalls && toolCalls.length) {
          msgs.push({role:"assistant", content:st.content || "", tool_calls:toolCalls});
          for (const tc of toolCalls) {
            if (abortSignal.aborted) throw new Error("aborted");
            const fn = tc.function;
            let args = {};
            try { args = JSON.parse(fn.arguments || "{}"); } catch(e) { args = { raw:fn.arguments }; }
            store.updateTask({ phase:"执行工具: "+fn.name });
            ui.updateStatusOnly();

            /* 工具调用重复检测（归一化参数） */
            const toolCallKey = normalizeToolCall(fn.name, args);
            if (toolCallKey === lastToolCall) {
              repeatToolCount++;
              if (repeatToolCount >= REPEAT_THRESHOLD) {
                await reflectAndAnswer(liveMsg, msgs, "重复调用同一工具", store, ui, MODEL, chatStream, abortSignal);
                if (!liveMsg.content) liveMsg.content = "（检测到重复调用同一工具，已自动停止。这个问题我暂时解决不了，你可以换个方式描述需求。）";
                store.updateTask({ phase:"停止-重复工具调用", step:stepCount });
                store.notify();
                return "";
              }
            } else {
              repeatToolCount = 0;
            }
            lastToolCall = toolCallKey;
            toolCallHistory.push(toolCallKey);

            /* 循环模式检测：ABAB 或 ABCABC */
            if (detectLoopPattern()) {
              await reflectAndAnswer(liveMsg, msgs, "工具调用循环模式", store, ui, MODEL, chatStream, abortSignal);
              if (!liveMsg.content) liveMsg.content = "（检测到工具调用陷入循环模式，已自动停止。你可以补充更多信息或换个方式提问。）";
              store.updateTask({ phase:"停止-循环模式", step:stepCount });
              store.notify();
              return "";
            }

            /* 搜索次数上限：达到后不再调用搜索，但继续执行任务其他步骤，不结束任务 */
            if (fn.name === "web_search") {
              searchCount++;
              if (searchCount > MAX_SEARCH_COUNT) {
                searchLimitReached = true;
                /* 不结束任务，只返回提示让模型基于已有信息继续执行后续步骤 */
                result = { ok: true, results: [], note: "已达到本任务搜索上限(" + MAX_SEARCH_COUNT + "次)，请基于已有信息继续执行任务的其他步骤，不要再次调用搜索。" };
                liveMsg._stepData.push({ tool: fn.name, args, result, time: Date.now() });
                ui.appendToolActivity(liveMsg, fn.name, args, result);
                stepCount++;
                continue;
              }
            }

            /* 危险操作需确认 */
            const risk = toolLayer.riskOf(fn.name);
            let result;
            if (risk >= 2) {
              const confirmed = await ui.confirmAction(fn.name, args);
              if (!confirmed) result = { ok:false, error:"用户拒绝执行" };
              else result = await toolLayer.exec(fn.name, Object.assign({}, args, {confirmed:true}), abortSignal);
            } else {
              result = await toolLayer.exec(fn.name, args, abortSignal);
            }

            /* 记录已读文件 */
            if (result && result.ok && (fn.name === "read_doc" || fn.name === "read_file" || fn.name === "stat_data") && args.path) readFiles.add(args.path);

            /* 强制回答更新：关键工具结果追加到回答中，确保用户能看到执行进度 */
            if (result && result.ok) {
              if (typeof liveMsg.content !== "string") liveMsg.content = String(liveMsg.content || "");
              let resultSummary = "";
              if (fn.name === "stat_data" && result.data) {
                const dataStr = JSON.stringify(result.data).substring(0, 500);
                resultSummary = "\n\n**统计结果**：" + dataStr;
              } else if (fn.name === "run_command" && result.stdout) {
                const outStr = String(result.stdout).substring(0, 800);
                resultSummary = "\n\n**执行结果**：\n```\n" + outStr + "\n```";
              } else if (fn.name === "read_doc" && result.preview) {
                resultSummary = "\n\n**文件已读取**：" + (result.rows || result.sheets || "内容已加载");
              } else if (fn.name === "create_doc" || fn.name === "feishu_create_doc") {
                resultSummary = "\n\n**文档已创建**：" + (result.url || result.doc_id || "成功");
              } else if (fn.name === "web_search" && result.results) {
                const count = Array.isArray(result.results) ? result.results.length : 0;
                resultSummary = "\n\n**搜索完成**：找到" + count + "条结果";
              }
              if (resultSummary && !liveMsg.content.includes(resultSummary.substring(0, 30))) {
                liveMsg.content += resultSummary;
                ui.streamUpdate(liveMsg.content);
              }
            }

            /* 无进展检测：工具结果重复（无新信息） */
            const resultStr = JSON.stringify(result).substring(0, 500);
            let resultHash = 0;
            for (let ci = 0; ci < resultStr.length; ci++) { resultHash = ((resultHash << 5) - resultHash + resultStr.charCodeAt(ci)) | 0; }
            if (toolResultHashes.has(resultHash)) {
              noProgressCount++;
              if (noProgressCount >= NO_PROGRESS_THRESHOLD) {
                // 无进展停止后，基于已有信息给出回答
                liveMsg.content = "（检测到连续多步无新信息，现在基于已有信息给出回答...）";
                store.updateTask({ phase:"总结回答-无进展", step:stepCount });
                store.notify();
                // 从思考过程提取回答，如果没有则用默认回答
                let answerFromThink = "";
                if (liveMsg._think) {
                  const thinkText = liveMsg._think;
                  const summaryIdx = thinkText.indexOf("【总结回答】");
                  if (summaryIdx >= 0) {
                    let summaryText = thinkText.substring(summaryIdx + 6);
                    const nextPhaseIdx = summaryText.indexOf("【");
                    if (nextPhaseIdx >= 0) summaryText = summaryText.substring(0, nextPhaseIdx);
                    summaryText = summaryText.trim();
                    if (summaryText) answerFromThink = summaryText;
                  }
                }
                if (!answerFromThink) {
                  // 从思考过程和工具结果中提取实际信息，生成个性化回答
                  let extractedInfo = [];
                  if (liveMsg._think) {
                    const thinkText = liveMsg._think;
                    const findPatterns = [
                      /找到了[^。\n]+/g, /确认了[^。\n]+/g, /发现[^。\n]+/g,
                      /搜索结果显示[^。\n]+/g, /根据搜索结果[^。\n]+/g,
                      /从搜索结果[^。\n]+/g, /包括[^。\n]+/g, /选手包括[^。\n]+/g
                    ];
                    for (const pattern of findPatterns) {
                      const matches = thinkText.match(pattern);
                      if (matches) {
                        for (const m of matches) {
                          if (m.length > 5 && m.length < 200 && !extractedInfo.includes(m)) extractedInfo.push(m);
                        }
                      }
                    }
                  }
                  if (liveMsg._stepData && liveMsg._stepData.length > 0) {
                    for (const step of liveMsg._stepData) {
                      if (step.tool === "web_search" && step.result) {
                        try {
                          const r = typeof step.result === "string" ? JSON.parse(step.result) : step.result;
                          if (r.results && r.results.length > 0) {
                            for (let i = 0; i < Math.min(2, r.results.length); i++) {
                              const item = r.results[i];
                              if (item.title && item.title.length > 5) {
                                const info = "搜索到：" + item.title.substring(0, 80);
                                if (!extractedInfo.includes(info)) extractedInfo.push(info);
                              }
                            }
                          }
                        } catch(e) {}
                      }
                    }
                  }
                  let answerParts = ["基于搜索结果的回答：", ""];
                  if (extractedInfo.length > 0) {
                    answerParts.push("从搜索中获取到的关键信息：");
                    for (let i = 0; i < Math.min(5, extractedInfo.length); i++) {
                      answerParts.push("- " + extractedInfo[i]);
                    }
                    answerParts.push("");
                  }
                  answerParts.push("搜索后部分关键数据未能完整获取。如果你需要更详细的信息，可以补充更具体的问题描述、时间范围或数据来源。");
                  answerFromThink = answerParts.join("\n");
                }
                liveMsg.content = answerFromThink;
                store.updateTask({ phase:"完成", step:stepCount });
                store.notify();
                return answerFromThink;
              }
            } else {
              noProgressCount = 0;
            }
            toolResultHashes.add(resultHash);

            msgs.push({role:"tool", content:JSON.stringify(result).slice(0, 8000), tool_call_id:tc.id});
            liveMsg._stepData.push({ step:stepCount, tool:fn.name, args, result });
            store.updateTask({ phase:"工具完成: "+fn.name });
            store.notify();  // 工具调用完成后全量渲染，显示活动框
          }
          continue;
        }

        /* 如果还有 pending 新需求，继续循环处理（不结束任务，下次迭代开头会创建新气泡+注入重规划） */
        if (store._pendingInstructions && store._pendingInstructions.length) {
          continue;
        }

        /* ===== 验证器：任务完成后对照目标自检 ===== */
        if (stepCount >= 2 && st.content && !store._verified) {
          try {
            store.updateTask({ phase:"验证中", step:stepCount });
            ui.updateStatusOnly();
            const goal = userText.substring(0, 300);
            const doneSummary = (liveMsg._stepData || []).map(sd => sd.tool).join("、");
            const verifyBody = { model:MODEL, messages:[
              {role:"system", content:"你是任务验证器。对照用户目标和已完成步骤，判断任务是否完成。严格按以下格式输出：\n【验证结果】完成/部分完成/未完成\n【缺失项】列出未完成的具体内容（没有就写无）\n【建议】下一步该怎么做（1-2句）"},
              {role:"user", content:"用户目标：" + goal + "\n已执行步骤：" + doneSummary + "\n模型回答：" + st.content.substring(0, 600)}
            ], max_tokens:300, chat_template_kwargs:{ enable_thinking:false } };
            const vOut = { content:"", reasoning:"", toolCalls:null, finish:null };
            try {
              await chatStream(verifyBody, {
                onToken: (c) => { vOut.content = c; },
                onReasoning: () => {},
              });
            } catch(e) {}
            if (vOut.content && vOut.content.trim()) {
              store._verified = true;
              /* 纯后台自检：只记录标记，不修改、不显示任何内容 */
              if (!liveMsg.content) liveMsg.content = st.content;
            }
          } catch(e) {}
        }

        /* 最终回答 */
        let answer = (liveMsg.content && liveMsg.content !== st.content ? liveMsg.content : (st.content || "")).trim();
        /* 如果 content 为空但思考过程里有"总结回答"阶段，从思考过程提取 */
        if (!answer && liveMsg._think) {
          const thinkText = liveMsg._think;
          const summaryIdx = thinkText.indexOf("【总结回答】");
          if (summaryIdx >= 0) {
            let summaryText = thinkText.substring(summaryIdx + 6);
            const nextPhaseIdx = summaryText.indexOf("【");
            if (nextPhaseIdx >= 0) summaryText = summaryText.substring(0, nextPhaseIdx);
            summaryText = summaryText.trim();
            if (summaryText) answer = summaryText;
          }
        }
        /* 兜底过滤：从最终回答中移除思考阶段标题（防止模型把思考过程混进答案） */
        answer = answer.replace(/【解析输入】[\s\S]*?(?=【信息调取】|【任务规划】|【分析推理】|【总结回答】|【完成情况】|$)/g, '')
                       .replace(/【信息调取】[\s\S]*?(?=【分析推理】|【总结回答】|【完成情况】|$)/g, '')
                       .replace(/【分析推理】[\s\S]*?(?=【总结回答】|【完成情况】|$)/g, '')
                       .replace(/【总结回答】[\s\S]*?(?=【完成情况】|$)/g, '')
                       .replace(/【完成情况】[\s\S]*?$/g, '')
                       .replace(/【任务规划】[\s\S]*?(?=【|$)/g, '')
                       .replace(/【调整计划】[\s\S]*?(?=【|$)/g, '')
                       .replace(/任务已完成[。！]?$/g, '')
                       .replace(/【完成情况】任务已完成[。！]?/g, '')
                       .trim();
        if (!answer) answer = (st.content || "").trim();  // 过滤后为空则用原始内容
        if (typeof answer !== "string") answer = JSON.stringify(answer);
        liveMsg.content = answer;
        /* token 统计：优先用 usage，没有则估算 */
        let promptTok = totalPrompt, compTok = totalComp;
        if (!promptTok && !compTok) {
          const inputText = msgs.map(m => m.content || "").join(" ");
          promptTok = Math.ceil(inputText.length * 0.6);
          compTok = Math.ceil(answer.length * 0.6);
        }
        store.state.tokens.session += promptTok + compTok;
        /* 空回复处理 */
        if (!liveMsg.content.trim()) {
          liveMsg.content = "（模型未返回有效内容，可能是请求超时或服务异常。请重试，或检查模型服务状态。）";
        }
        /* 记忆更新：完成任务自动沉淀一条经验 */
        if (store.state.settings.autoMemory && stepCount >= 2 && answer.trim().length > 30) {
          try {
            const memText = "完成了一次任务：" + userText.substring(0, 40) + "（执行了" + stepCount + "步工具，包括" + (liveMsg._stepData||[]).map(sd=>sd.tool).slice(0,4).join("、") + "）";
            if (store.state.memory.length < 50) {
              store.state.memory.push(memText);
              store.saveMemory();
            }
          } catch(e) {}
        }
        store.updateTask({ phase:"完成", step:stepCount });
        store.notify();
        return answer;
      }
      liveMsg.content = "（已达到最大工具调用步数 "+maxSteps+"，任务可能未完全完成。你可以继续补充需求，我会接着处理。）";
      store.notify();
      return "";
    } catch(e) {
      const msg = String(e.message || e);
      console.error("任务执行失败：", msg);
      if (msg.includes("abort") || msg.includes("Abort")) liveMsg.content = "（任务已停止）";
      else {
        let errorMsg = "出错了：" + msg;
        if (msg.includes("Failed to fetch") || msg.includes("fetch") || msg.includes("连接") || msg.includes("network")) {
          errorMsg += "\n\n⚠️ 可能是服务未运行或崩溃了。请：\n1. 运行 启动RuiAI.bat 重启服务\n2. 或刷新页面重试\n3. 检查端口 8080(模型) 和 8082(工具) 是否被占用";
        }
        liveMsg.content = errorMsg;
      }
      // 显式结束任务，确保状态被正确清理（关键：防止UI仍然显示"启动中"）
      store.endTask();
      store.saveConvs();
      store.notify();
      return "";
    } finally {
      // 确保思考过程被保存到liveMsg（关键：防止思考过程丢失）
      if (liveMsg._think && liveMsg._think.trim()) {
        console.log("思考过程已保存，长度：", liveMsg._think.length);
      }
      // 只有当前会话还是任务所属会话时才更新UI
      if (store.state.currentConvId === convId) {
        store.saveConvs();
      } else {
        console.log("会话已切换，不更新UI");
      }  /* 生成完成统一保存，刷新不丢内容 */
      store.endTask();
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
      ui.resetScrollState();  /* 生成完成后重置滚动状态，允许后续新消息自动滚动 */
    }
  },

  /* 普通对话模式：纯对话 + 发送前自动联网搜索一次，不进入工具调用循环、不展示思考 */
  async runNormal(userText, convId) {
    const conv = store.state.convs.find(c => c.id === convId);
    if (!conv) return "";
    store.startTask(convId);
    const abortSignal = store.state.task.abortCtrl.signal;
    store.addMessage(convId, {role:"user", content:userText, _mode:"normal"});
    const liveMsg = { role:"assistant", content:"", _think:"", _mode:"normal" };
    store.addMessage(convId, liveMsg);
    store.notify();

    store.state.genSpeed = 0; store.state.genTokens = 0; store.state.genStartTime = 0;

    /* 普通模式基础提示词：事实约束 + 格式规范（不依赖170行Agent提示词） */
    let sysPrompt = `你是 Rui AI，运行在用户本地电脑上的智能助手（普通对话模式，不调用工具，可自动联网）。

【回答要求】
- 直接给成品答案：先结论后展开，干净、完整、可直接阅读，不要输出思考过程，也不要说"作为AI"之类的套话
- 简单问题简短回答，复杂问题分点或用表格结构化回答，关键信息加粗
- 不确定的信息明确标注"推测"或"无法确认"，绝不编造具体数据、新闻事件、人物履历或来源链接
- 若系统提供了联网资料，优先依据资料回答并可标注来源名称；资料不足时明确说明，不要硬编
- 对比类问题用表格并给明确结论；步骤类问题编号分点
- 涉及健康/医疗/法律/投资的内容只给一般性参考，并建议咨询专业人士`;
    if (store.state.settings.autoMemory && store.state.memory.length) {
      sysPrompt += "\n\n【用户长期记忆】\n" + store.state.memory.map((mm,k) => (k+1)+". "+mm).join("\n");
    }
    /* 普通模式也支持已上传的文本文件（直接把内容注入提示词；二进制文档需切到Agent模式） */
    if (store.state.loadedFiles && store.state.loadedFiles.length) {
      const textFiles = store.state.loadedFiles.filter(f => f.content);
      if (textFiles.length) {
        sysPrompt += "\n\n【用户上传的文本文件内容】\n" + textFiles.map(f => "文件: " + f.name + "\n内容:\n" + String(f.content).substring(0, 8000)).join("\n\n---\n\n");
      }
    }

    /* 上下文截断：按总字符数截断（最多3000字符），避免长散文/思考过程撑爆上下文导致prefill暴增 */
    const historyAll = conv.messages.slice(0,-1).map(m => ({role:m.role, content:m.content}));
    let history = historyAll;
    let totalChars = history.reduce((s,m) => s + (m.content?m.content.length:0), 0);
    while (history.length > 2 && totalChars > 3000) {
      history = history.slice(1);
      totalChars = history.reduce((s,m) => s + (m.content?m.content.length:0), 0);
    }
    const msgs = [{role:"system", content:sysPrompt}, ...history];

    /* 从可能带"文件前缀"的文本里提取用户真正的问题作为搜索词 */
    const searchQuery = userText.includes("\n\n") ? userText.slice(userText.lastIndexOf("\n\n")+2).trim() : userText;
    /* 极短问候/感谢/道别不联网，其余问题默认自动搜一次（本地9B知识有限，宁搜勿编） */
    const isSmallTalk = (q) => {
      const t = String(q||"").replace(/[\s，。！？、~.!?？]/g,"").toLowerCase();
      if (!t || t.length > 10) return false;
      return /^(你好|您好|hi|hello|hey|哈喽|嗨|在吗|在不在|谢谢|感谢|多谢|thanks|thankyou|再见|拜拜|bye|goodbye|早上好|下午好|中午好|晚上好|晚安|早安)$/.test(t);
    };

    let searchedCount = 0;
    /* 普通模式自动联网搜索：默认关闭，避免每次提问都先爬搜索引擎导致等待几十秒。需要时在设置中开启 */
    const autoSearch = store.state.settings.autoSearch === true;  // 默认关闭，只有设置中显式开启才搜索
    if (autoSearch && !isSmallTalk(searchQuery)) {
      try {
        store.updateTask({ phase:"自动联网搜索中" });
        ui.updateStatusOnly();
        const sw = await toolLayer.exec("web_search", { query:searchQuery, n:5 }, abortSignal);
        const results = (sw && Array.isArray(sw.results)) ? sw.results : [];
        searchedCount = results.length;
        if (results.length) {
          const text = results.slice(0,5).map((r,k) => (k+1)+". 《"+r.title+"》"+(r.snippet?("\n"+r.snippet):"")+(r.url?("\n来源："+r.url):"")).join("\n\n");
          msgs[0].content += "\n\n【本次自动联网搜索到的参考资料】\n"+text+"\n\n请优先依据以上资料回答，关键结论可标注来源名称；资料中没有的信息不要编造。";
        } else {
          msgs[0].content += "\n\n【联网状态】本次自动搜索未获取到有效资料。可基于已有知识回答，但对不确定的事实必须明确标注'无法联网核实'，不要编造具体数据、新闻或来源。";
        }
      } catch(eSearch) {
        msgs[0].content += "\n\n【联网状态】搜索过程中断。基于已有知识谨慎回答，不确定的事实明确标注'无法联网核实'。";
      }
    }

    try {
      store.updateTask({ phase: searchedCount ? ("已联网"+searchedCount+"条·生成中") : "生成中" });
      ui.updateStatusOnly();
      /* 普通模式：关闭思考、不传tools，保证轻快的纯对话体验 */
      const body = { model:MODEL, messages:msgs, max_tokens:8192, stream_options:{include_usage:true}, chat_template_kwargs:{ enable_thinking:false } };
      const st = await chatStream(body, {
        onToken: (c) => {
            liveMsg.content = typeof c === "string" ? c : String(c || ""); ui.streamUpdate(liveMsg.content); ui.updateStatusOnly();
            if (!store.state.genStartTime) { store.state.genStartTime = Date.now(); store.state.genTokens = 0; }
            store.state.genTokens++;
            const elapsed = (Date.now() - store.state.genStartTime) / 1000;
            if (elapsed > 0.5) { store.state.genSpeed = store.state.genTokens / elapsed; ui.updateStatusOnly(); }
          },
      });
      liveMsg.content = st.content || "";
      /* length截断检测：回答被max_tokens截断时，自动补全一次（普通模式最多补1次） */
      if (st.finish === "length" && liveMsg.content.trim()) {
        store.updateTask({ phase:"补全回答中(token截断)" });
        ui.updateStatusOnly();
        msgs.push({role:"assistant", content:liveMsg.content});
        msgs.push({role:"user", content:"请继续完成上面的回答，直接接着写，不要重复已有的内容。"});
        const body2 = { model:MODEL, messages:msgs, max_tokens:8192, stream_options:{include_usage:true}, chat_template_kwargs:{ enable_thinking:false } };
        const st2 = await chatStream(body2, {
          onToken: (c) => { liveMsg.content = (st.content || "") + (typeof c === "string" ? c : String(c || "")); ui.streamUpdate(liveMsg.content); ui.updateStatusOnly(); },
        });
        liveMsg.content = (st.content || "") + (st2.content || "");
      }
      let sessTok = 0;
      if (st.usage) sessTok = (st.usage.prompt_tokens||0) + (st.usage.completion_tokens||0);
      else sessTok = Math.ceil((msgs.map(m=>m.content||"").join(" ").length + (st.content||"").length) * 0.6);
      store.state.tokens.session += sessTok;
      if (!liveMsg.content.trim()) {
        liveMsg.content = "（模型未返回有效内容，可能是请求超时或服务异常。请重试，或检查模型服务状态。）";
      }
      ui.renderMessages();
      return st.content || "";
    } catch(e) {
      const msg = String(e.message || e);
      if (msg.includes("abort") || msg.includes("Abort")) liveMsg.content = "（已停止）";
      else {
        let errorMsg = "出错了：" + msg;
        if (/Failed to fetch|fetch|连接|network/i.test(msg)) {
          errorMsg += "\n\n⚠️ 可能是服务未运行或崩溃了。请：\n1. 运行 启动RuiAI.bat 重启服务\n2. 或刷新页面重试\n3. 检查端口 8080(模型) 和 8082(工具) 是否被占用";
        }
        liveMsg.content = errorMsg;
      }
      ui.renderMessages();
      return "";
    } finally {
      store.saveConvs();
      store.endTask();
      ui.renderMessages();
      ui.resetScrollState();
    }
  },

};

/* ================= UI Renderer：数据驱动 ================= */
/**
 * UI渲染对象（单例模式）
 * 负责：消息渲染、会话列表渲染、输入框处理、流式更新、滚动管理
 * 采用增量更新策略，避免频繁全量重渲染
 * 
 * 主要属性：
 * - els: DOM元素缓存
 * - userScrolling: 用户手动滚动标志
 * - jsScrolling: 程序自动滚动标志
 * - _streamText: 流式文本缓存
 * - _streamPending: 流式更新待处理标志
 */
const ui = {
  els: {},
  // 滚动状态：区分用户手动滚动和程序自动滚动
  userScrolling: false,
  jsScrolling: false,
  init() {
    this.els = {
      convList: document.getElementById("convList"),
      messages: document.getElementById("messages"),
      input: document.getElementById("input"),
      send: document.getElementById("send"),
      stop: document.getElementById("stop"),
      newChat: document.getElementById("newChat"),
      modeNormal: document.getElementById("modeNormal"),
      modeAgent: document.getElementById("modeAgent"),
      statTotal: document.getElementById("statTotal"),
      modelLabel: document.getElementById("modelLabel"),
      statusDot: document.getElementById("statusDot"),
      clearBtn: document.getElementById("clearBtn"),
      menuBtn: document.getElementById("menuBtn"),
      sidebar: document.getElementById("sidebar"),
      memBtn: document.getElementById("memBtn"),
      setBtn: document.getElementById("setBtn"),
      settingsModal: document.getElementById("settingsModal"),
      memoryModal: document.getElementById("memoryModal"),
      settingsClose: document.getElementById("settingsClose"),
      memClose: document.getElementById("memClose"),
      memInput: document.getElementById("memInput"),
      memAdd: document.getElementById("memAdd"),
      memList: document.getElementById("memList"),
      maxSteps: document.getElementById("maxSteps"),
      modelSelect: document.getElementById("modelSelect"),
      resetAll: document.getElementById("resetAll"),
      modal: document.getElementById("modal"),
      modalCmd: document.getElementById("modalCmd"),
      modalAllow: document.getElementById("modalAllow"),
      modalDeny: document.getElementById("modalDeny"),
      hint: document.getElementById("hint"),
      attach: document.getElementById("attach"),
      attachImg: document.getElementById("attachImg"),
      fileInput: document.getElementById("fileInput"),
      imgInput: document.getElementById("imgInput"),
      fileinfo: document.getElementById("fileinfo"),
      filename: document.getElementById("filename"),
      filechars: document.getElementById("filechars"),
      pendingImg: document.getElementById("pendingImg"),
      memDot: document.getElementById("memDot"),
      themeBtn: document.getElementById("themeBtn"),
    };
    this.bindEvents();
    this.initTheme();
    this.initScrollListener();
    store.subscribe(() => this.render());
    this.render();
    this.loadModels();  // 页面初始化时从后端加载模型列表，同步顶部模型名称显示
  },

  // 初始化滚动监听：区分用户手动滚动和程序自动滚动
  initScrollListener() {
    if (!this.els.messages) return;
    this.els.messages.addEventListener('scroll', () => {
      // 如果是程序正在自动滚动，则不标记为用户滚动
      if (this.jsScrolling) {
        this.jsScrolling = false;
        return;
      }
      // 用户手动滚动时，标记为用户滚动，暂停自动滚动
      this.userScrolling = true;
    });
  },

  // 智能滚动到底部：只有用户没有手动滚动时才自动滚动
  /**
   * 智能滚动到底部
   * 只有用户没有手动滚动时才自动滚动
   * 使用requestAnimationFrame优化滚动性能
   */
  smartScrollToBottom() {
    if (!this.els.messages) return;
    // 如果用户正在手动滚动，则不自动滚动
    if (this.userScrolling) return;
    // 标记为程序自动滚动
    this.jsScrolling = true;
    // 使用requestAnimationFrame确保滚动在渲染后执行
    requestAnimationFrame(() => {
      this.els.messages.scrollTo({
        top: this.els.messages.scrollHeight,
        behavior: 'smooth'
      });
    });
  },

  // 重置滚动状态：消息生成完成后调用，允许后续新消息触发自动滚动
  resetScrollState() {
    this.userScrolling = false;
    this.jsScrolling = false;
  },

  bindEvents() {
    this.els.send.addEventListener("click", () => this.sendMessage());
    this.els.input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.sendMessage(); } });
    this.els.input.addEventListener("input", () => this.autoResize());
    this.els.stop.addEventListener("click", () => this.stopTask());
    this.els.newChat.addEventListener("click", () => { store.addConv(); this.els.input.focus(); });
    this.els.clearBtn.addEventListener("click", () => { const c = store.getCurrentConv(); if (c) { c.messages = []; store.saveConvs(); store.notify(); } });
    this.els.menuBtn.addEventListener("click", () => this.els.sidebar.classList.toggle("hidden"));
    this.els.modeNormal.addEventListener("click", () => { this.setMode("normal"); });
    this.els.modeAgent.addEventListener("click", () => { this.setMode("agent"); });
    this.els.setBtn.addEventListener("click", () => this.openSettings());
    this.els.settingsClose.addEventListener("click", () => this.els.settingsModal.classList.remove("show"));
    this.els.memBtn.addEventListener("click", () => this.openMemory());
    this.els.memClose.addEventListener("click", () => this.els.memoryModal.classList.remove("show"));
    this.els.memAdd.addEventListener("click", () => this.addMemory());
    this.els.maxSteps.addEventListener("change", () => { store.state.settings.maxSteps = parseInt(this.els.maxSteps.value) || MAX_STEPS_DEFAULT; store.saveSettings(); });
    this.els.modelSelect.addEventListener("change", () => this.switchModel());
    this.els.resetAll.addEventListener("click", () => { if (confirm("确定清空所有数据？")) { localStorage.clear(); location.reload(); } });
    this.els.modalAllow.addEventListener("click", () => { this._modalResolve && this._modalResolve(true); this.els.modal.classList.remove("show"); });
    this.els.modalDeny.addEventListener("click", () => { this._modalResolve && this._modalResolve(false); this.els.modal.classList.remove("show"); });
    this.els.attach.addEventListener("click", () => this.els.fileInput.click());
    this.els.attachImg.addEventListener("click", () => this.els.imgInput.click());
    this.els.fileInput.addEventListener("change", (e) => this.handleFileUpload(e));
    this.els.imgInput.addEventListener("change", (e) => this.handleImgUpload(e));

    /* 设置面板的 mini 开关 */
    document.getElementById("swAutoMemory").addEventListener("click", function() { this.classList.toggle("on"); store.state.settings.autoMemory = this.classList.contains("on"); store.saveSettings(); });

    /* 深色模式切换 */
    if (this.els.themeBtn) {
      console.log("深色模式按钮事件监听器已绑定");
      this.els.themeBtn.addEventListener("click", () => {
        console.log("深色模式按钮被点击");
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "light" ? "dark" : "light";
        this.applyTheme(next);
        localStorage.setItem("rui_theme", next);
        console.log("主题已切换为:", next);
      });
    } else {
      console.log("深色模式按钮不存在");
    }
  },

  /* 发送消息 */
  async sendMessage() {
    const text = this.els.input.value.trim();
    if (!text) return;
    /* 任务执行中：Agent模式注入当前任务重规划；普通模式是一次性请求，不支持注入，仅提示稍候 */
    if (store.state.busy && store.state.task) {
      if (store.state.settings.mode !== 'agent') {
        const waitHint = document.createElement("div");
        waitHint.className = "inject-hint";
        waitHint.textContent = "正在生成回答，请稍候…";
        this.els.input.parentElement.appendChild(waitHint);
        setTimeout(() => waitHint.remove(), 2000);
        return;
      }
      const ok = this.sendInstruction(text);
      if (ok) {
        this.els.input.value = "";
        this.els.input.style.height = "auto";
        /* 显示一个轻量提示，告诉用户已注入 */
        const hint = document.createElement("div");
        hint.className = "inject-hint";
        hint.textContent = "已加入当前任务，继续处理中…";
        this.els.input.parentElement.appendChild(hint);
        setTimeout(() => hint.remove(), 2500);
      }
      return;
    }
    this.els.input.value = "";
    this.els.input.style.height = "auto";
    /* 不隐藏fileinfo：保持显示已上传文件，用户可随时看到哪些文件已加载 */
    const convId = store.state.currentConvId;
    /* 把已上传文件信息附加到消息中，保存到对话历史，任务中断后不丢失 */
    let finalText = text;
    if (store.state.loadedFiles && store.state.loadedFiles.length) {
      const fileInfo = store.state.loadedFiles.map(f => {
        if (f.path && f.needTool) return "📎 文件：" + f.name + "\n路径：" + f.path + "\n（请用 read_doc 工具读取此文件）";
        return "📎 文件：" + f.name;
      }).join("\n\n");
      finalText = fileInfo + "\n\n" + text;
    }
    if (store.state.settings.mode === 'agent') await agentEngine.run(finalText, convId);
    else await agentEngine.runNormal(finalText, convId);
    /* 不在任务完成后清空loadedFiles：保持会话期间文件可用，中断后继续不丢失；仅在新建会话时清空 */
  },

  /* 任务执行中发送新指令（注入当前任务，触发重规划） */
  sendInstruction(text) {
    if (!store.state.busy || !store.state.task) return false;
    /* 去重：防止Enter+click同时触发导致重复气泡 */
    const conv = store.state.convs.find(c => c.id === store.state.task.convId);
    const lastMsg = conv && conv.messages.length ? conv.messages[conv.messages.length - 1] : null;
    if (lastMsg && lastMsg.role === "user" && lastMsg.content === text) {
      if (!store._pendingInstructions) store._pendingInstructions = [];
      store._pendingInstructions.push(text);
      store.notify();
      return true;
    }
    if (!store._pendingInstructions) store._pendingInstructions = [];
    store._pendingInstructions.push(text);
    store.addMessage(store.state.task.convId, { role:"user", content:text });
    store.notify();
    /* 显示轻量提示：已纳入当前任务，正在重新规划 */
    const hint = document.createElement("div");
    hint.className = "inject-hint";
    hint.textContent = "已纳入当前任务，正在重新规划…";
    this.els.input.parentElement.appendChild(hint);
    setTimeout(() => hint.remove(), 2500);
    return true;
  },

  stopTask() {
    if (store.state.task && store.state.task.abortCtrl) {
      try { store.state.task.abortCtrl.abort(); } catch(e) {}
    }
    store.state.task = null;
    store.state.busy = false;
    // 清理流式输出状态
    this._streamText = "";
    this._streamPending = false;
    this._streamLen = 0;
    store.notify();
  },

  /* 危险操作确认：人性化标题 + 风险等级 + 关键参数，60秒无操作自动拒绝 */
  confirmAction(toolName, args) {
    return new Promise((resolve) => {
      let settled = false;
      const timer = setTimeout(() => finish(false), 60000);
      const finish = (v) => { if (settled) return; settled = true; clearTimeout(timer); this.els.modal.classList.remove("show"); resolve(v); };
      this._modalResolve = finish;
      const label = TOOL_CONFIRM_LABELS[toolName] || { title: toolName, desc: () => JSON.stringify(args).substring(0,150) };
      const risk = toolLayer.riskOf(toolName);
      const riskText = risk >= 3 ? "⚠️ 高风险" : risk >= 2 ? "⚡ 中等风险" : "📝 一般操作";
      this.els.modalCmd.innerHTML =
        '<div style="font-weight:600;margin-bottom:6px;font-size:15px">' + this.escape(label.title) +
        ' <span style="font-size:11px;color:var(--muted);font-weight:400;margin-left:6px">' + riskText + '</span></div>' +
        '<div style="font-size:13px;color:var(--text2);word-break:break-all;line-height:1.5">' + this.escape(label.desc(args||{})) + '</div>' +
        '<div style="font-size:11px;color:var(--muted);margin-top:10px;border-top:1px solid var(--border);padding-top:6px">60秒无操作将自动拒绝 · 请确认后再执行</div>';
      this.els.modal.classList.add("show");
    });
  },

  /* 设置 */
  openSettings() {
    this.els.maxSteps.value = store.state.settings.maxSteps;
    this.loadModels();
    document.getElementById("swAutoMemory").classList.toggle("on", store.state.settings.autoMemory);
    const ml = document.getElementById("modeLabel");
    if (ml) ml.textContent = store.state.settings.mode === "agent" ? "Agent" : "普通";
    this.els.settingsModal.classList.add("show");
  },

  /* 模型切换：从后端加载可用模型列表填充下拉框 */
  async loadModels() {
    try {
      const r = await fetch(AGENT_API + "/api/models", { headers: { "X-Access-Token": ACCESS_TOKEN } });
      const d = await r.json();
      const sel = this.els.modelSelect;
      sel.innerHTML = "";
      for (const [key, info] of Object.entries(d.models || {})) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = info.name + (info.exists ? "" : "（文件不存在）");
        opt.disabled = !info.exists;
        if (key === d.current || key === store.state.settings.model) {
          opt.selected = true;
          // 根据当前模型设置思考模式开关
          currentModelThinking = (info.thinking !== false);
          // 同步更新顶部模型名称显示
          if (this.els.modelLabel) this.els.modelLabel.textContent = info.name + " · 本地运行";
        }
        sel.appendChild(opt);
      }
    } catch (e) { /* 后端不可达时忽略 */ }
  },

  /* 模型切换：调用后端重启 llama-server，等待就绪 */
  async switchModel() {
    const sel = this.els.modelSelect;
    const key = sel.value;
    if (!key || key === store.state.settings.model) return;
    if (store.state.busy) { alert("任务进行中，请先停止当前任务再切换模型"); sel.value = store.state.settings.model; return; }
    const label = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : key;
    if (!confirm("切换到 " + label + "？\n模型服务将重启，约需25秒，期间无法对话。")) { sel.value = store.state.settings.model; return; }
    this.els.input.disabled = true; this.els.send.disabled = true;
    this.els.hint.textContent = "正在切换模型到 " + label + "，约25秒…";
    try {
      const r = await fetch(AGENT_API + "/api/switch_model", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Access-Token": ACCESS_TOKEN },
        body: JSON.stringify({ model: key })
      });
      const d = await r.json();
      if (d.ok) {
        store.state.settings.model = key; store.saveSettings();
        // 切换模型后更新思考模式开关
        const sel2 = this.els.modelSelect;
        const selectedOpt = sel2.options[sel2.selectedIndex];
        // 从后端重新获取模型信息以确认 thinking 属性
        try {
          const mr = await fetch(AGENT_API + "/api/models", { headers: { "X-Access-Token": ACCESS_TOKEN } });
          const md = await mr.json();
          if (md.models && md.models[key]) currentModelThinking = (md.models[key].thinking !== false);
        } catch(e) { /* 忽略 */ }
        this.els.hint.textContent = "已切换到 " + (d.name || key) + "（就绪耗时 " + (d.ready_after || "?") + "）";
        // 同步更新顶部模型名称显示
        if (this.els.modelLabel) this.els.modelLabel.textContent = (d.name || key) + " · 本地运行";
        setTimeout(() => { this.els.hint.textContent = ""; }, 6000);
      } else {
        alert("切换失败：" + (d.error || "未知错误"));
        sel.value = store.state.settings.model;
      }
    } catch (e) {
      alert("切换请求失败：" + e.message);
      sel.value = store.state.settings.model;
    } finally {
      this.els.input.disabled = false; this.els.send.disabled = false;
    }
  },

  /* 记忆 */
  openMemory() { this.renderMemoryList(); this.els.memoryModal.classList.add("show"); },
  addMemory() {
    const text = this.els.memInput.value.trim();
    if (!text) return;
    store.state.memory.push(text);
    store.saveMemory();
    this.els.memInput.value = "";
    this.renderMemoryList();
  },
  renderMemoryList() {
    this.els.memList.innerHTML = store.state.memory.map((m,i) =>
      '<div class="mem-item"><span>'+this.escape(m)+'</span><button data-i="'+i+'">删除</button></div>'
    ).join("");
    this.els.memList.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", () => { store.state.memory.splice(parseInt(btn.dataset.i),1); store.saveMemory(); this.renderMemoryList(); });
    });
    this.els.memDot.style.display = store.state.memory.length ? "inline-block" : "none";
  },

  /* 文件上传 */
  handleFileUpload(e) {
    const files = e.target.files;
    if (!files || !files.length) return;
    const textExts = [".txt",".md",".csv",".json",".py",".js",".html",".css",".xml",".yaml",".yml",".ini",".conf",".sh",".bat",".ps1",".log"];
    const binExts = [".doc",".docx",".xls",".xlsx",".ppt",".pptx",".pdf",".rtf"];
    let totalChars = 0;
    const names = [];
    for (const f of files) {
      names.push(f.name);
      const ext = "." + f.name.split(".").pop().toLowerCase();
      if (textExts.includes(ext)) {
        /* 文本文件：直接读取内容 */
        const reader = new FileReader();
        reader.onload = (ev) => {
          const content = ev.target.result;
          totalChars += content.length;
          store.state.loadedFiles.push({ name:f.name, content:content.slice(0, 50000) });
          this.els.filechars.textContent = "约 " + totalChars.toLocaleString() + " 字符";
        };
        reader.readAsText(f);
      } else {
        /* 二进制文件：上传到后端，显示状态但不禁用发送 */
        this.els.filechars.textContent = "上传中: " + f.name + "...";
        const uiRef = this;
        fetch(AGENT_API + "/api/upload?name=" + encodeURIComponent(f.name), {
          method: "POST",
          body: f,
        }).then(r => r.json()).then(data => {
          if (data && data.path) {
            store.state.loadedFiles.push({ name:f.name, path:data.path, needTool:true, size:f.size });
            uiRef.els.filechars.textContent = "已上传: " + f.name + " (" + Math.round(f.size/1024) + "KB)";
          } else {
            uiRef.els.filechars.textContent = "上传失败: " + f.name;
          }
        }).catch(err => {
          uiRef.els.filechars.textContent = "上传失败: " + f.name;
        });
      }
    }
    this.els.filename.textContent = names.join(", ");
    this.els.fileinfo.classList.add("show");
    e.target.value = "";
  },
  handleImgUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      store.state.pendingImg = ev.target.result;
      this.els.pendingImg.innerHTML = '<img src="'+ev.target.result+'" style="max-width:120px;max-height:120px;border-radius:10px;border:1px solid var(--border)">';
      this.els.pendingImg.classList.add("show");
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  },

  autoResize() {
    // 防抖：避免频繁调整高度
    if (this._resizeTimer) clearTimeout(this._resizeTimer);
    this._resizeTimer = setTimeout(() => {
      this.els.input.style.height = "auto";
      this.els.input.style.height = Math.min(this.els.input.scrollHeight, 200) + "px";
    }, 50);
  },

  /* ========== 渲染 ========== */
  render() {
    this.renderConvList();
    this.renderMessages();
    this.renderHeader();
  },

  renderConvList() {
    const html = store.state.convs.map(c => {
      const active = c.id === store.state.currentConvId ? " active" : "";
      const running = store.state.task && store.state.task.convId === c.id ? '<span class="conv-running">执行中</span>' : "";
      return '<div class="conv'+active+'" data-id="'+c.id+'"><span class="t">'+this.escape(c.title)+running+'</span><button class="del" data-id="'+c.id+'">✕</button></div>';
    }).join("");
    this.els.convList.innerHTML = html;
    this.els.convList.querySelectorAll(".conv").forEach(el => {
      el.addEventListener("click", (e) => { if (!e.target.classList.contains("del")) store.switchConv(el.dataset.id); });
    });
    this.els.convList.querySelectorAll(".del").forEach(btn => {
      btn.addEventListener("click", (e) => { e.stopPropagation(); store.deleteConv(btn.dataset.id); });
    });
  },

  renderMessages() {
    const conv = store.getCurrentConv();
    if (!conv || !conv.messages.length) {
      this.els.messages.innerHTML = this.welcomeHTML();
      return;
    }
    const html = conv.messages.map(m => this.renderMessage(m)).join("");
    this.els.messages.innerHTML = html;
    /* 绑定用户消息的编辑/复制按钮 */
    this.els.messages.querySelectorAll(".msg.user").forEach((msgEl, idx) => {
      const copyBtn = msgEl.querySelector(".ma-copy");
      const editBtn = msgEl.querySelector(".ma-edit");
      if (copyBtn) copyBtn.addEventListener("click", () => {
        const text = conv.messages.filter(m => m.role === "user")[idx]?.content || "";
        navigator.clipboard.writeText(text).catch(() => {});
      });
      if (editBtn) editBtn.addEventListener("click", () => this.startEdit(msgEl, conv, idx));
    });

    /* 绑定助手消息的复制/重新生成按钮 */
    this.els.messages.querySelectorAll(".msg.assistant").forEach((msgEl, idx) => {
      const asstMsgs = conv.messages.filter(m => m.role === "assistant");
      const copyBtn = msgEl.querySelector(".asst-copy");
      const regenBtn = msgEl.querySelector(".asst-regen");
      if (copyBtn) copyBtn.addEventListener("click", () => {
        const text = asstMsgs[idx]?.content || "";
        navigator.clipboard.writeText(text).catch(() => {});
      });
      if (regenBtn) regenBtn.addEventListener("click", () => {
        if (store.state.busy) return;
        /* 找到这条助手消息对应的用户消息，截断后重新发送 */
        const asstMsg = asstMsgs[idx];
        const msgIdx = conv.messages.indexOf(asstMsg);
        if (msgIdx > 0) {
          const userMsg = conv.messages[msgIdx - 1];
          if (userMsg && userMsg.role === "user") {
            conv.messages = conv.messages.slice(0, msgIdx - 1);
            store.saveConvs();
            this.renderMessages();
            setTimeout(() => {
              if (store.state.settings.mode === 'agent') agentEngine.run(userMsg.content, store.state.currentConvId);
              else agentEngine.runNormal(userMsg.content, store.state.currentConvId);
            }, 100);
          }
        }
      });
    });
    /* 代码块复制按钮：事件委托（每次renderMessages重新绑定，因为innerHTML重建了DOM） */
    this.els.messages.querySelectorAll(".code-copy").forEach(btn => {
      btn.addEventListener("click", () => {
        const code = btn.parentElement.querySelector("code");
        if (code) {
          navigator.clipboard.writeText(code.textContent).then(() => {
            btn.textContent = "已复制"; btn.classList.add("copied");
            setTimeout(() => { btn.textContent = "复制"; btn.classList.remove("copied"); }, 1500);
          }).catch(() => {});
        }
      });
    });
    // 使用智能滚动：只有用户没有手动滚动时才自动滚动
    this.smartScrollToBottom();
  },

  /**
   * 从工具调用结果/参数中提取本地文件路径，用于在UI中显示下载/预览链接
   * 检测已知字段 + 从结果JSON中正则提取 Windows 路径
   */
  extractFilePaths(sd) {
    const paths = new Set();
    const exts = /\.(docx?|xlsx?|pptx?|pdf|png|jpe?g|gif|webp|bmp|txt|md|csv|json|html?|zip|rar|7z|mp3|mp4|wav|py|js|ts|css|xml|yml|yaml)$/i;
    const candidates = [];
    // 已知字段：result 和 args 中的路径字段
    const pathKeys = ["path","file","file_path","filepath","output","save_path","out","filename","file_name"];
    if (sd.result) for (const k of pathKeys) { if (sd.result[k] && typeof sd.result[k] === "string") candidates.push(sd.result[k]); }
    if (sd.args) for (const k of pathKeys) { if (sd.args[k] && typeof sd.args[k] === "string") candidates.push(sd.args[k]); }
    // 从结果JSON中正则提取 Windows 路径（D:\... 或 C:/...）
    if (sd.result) {
      const resultStr = JSON.stringify(sd.result);
      const re = /[A-Za-z]:[\\/][^\s"\'\]\)}\<>|]+\.[A-Za-z0-9]{1,6}/g;
      let m;
      while ((m = re.exec(resultStr)) !== null) candidates.push(m[0]);
    }
    // 过滤：必须是 Windows 绝对路径且有已知扩展名；规范化路径分隔符（双反斜杠→单反斜杠）后去重
    for (const p of candidates) {
      if (!p || typeof p !== "string") continue;
      const clean = p.replace(/\\+/g, "\\").replace(/\/+/g, "/").replace(/^["']|["']$/g, "");
      if (exts.test(clean) && /^[A-Za-z]:[\\/]/.test(clean)) paths.add(clean);
    }
    return Array.from(paths);
  },

  /**
   * 渲染单条消息为HTML
   * 支持用户消息、助手消息、系统消息
   * 助手消息包含：思考过程折叠面板、工具调用折叠面板、回答内容、操作按钮
   * @param {Object} m - 消息对象 {role, content, _think, _stepData, _reflect}
   * @returns {string} HTML字符串
   */
  renderMessage(m) {
    if (m.role === "user") {
      return '<div class="msg user"><div class="avatar">你</div><div class="col"><div class="bubble">'+this.escape(m.content)+'</div><div class="msg-actions"><button class="ma-btn ma-copy" title="复制"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button><button class="ma-btn ma-edit" title="编辑"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></div></div></div>';
    }
    if (m.role === "system") {
      return '<div class="msg system"><div class="col"><div class="bubble">'+this.escape(m.content)+'</div></div></div>';
    }
    /* assistant - 简约 agent 执行流程 */
    let stepsHtml = "";
    if (m._stepData && m._stepData.length) {
      // 统计成功/失败数量
      const okCount = m._stepData.filter(sd => sd.result && !sd.result.error).length;
      const errCount = m._stepData.length - okCount;
      const statusText = errCount > 0 ? okCount + "成功 " + errCount + "失败" : okCount + " 步成功";
      
      // 所有工具调用放在一个折叠面板里（参考豆包/ChatGPT设计）
      // 折叠面板显示：工具调用数量、成功/失败状态、展开后显示详细信息
      stepsHtml = '<details class="agent-steps-wrapper" open>';
      stepsHtml += '<summary class="agent-steps-header">';
      stepsHtml += '<span class="agent-steps-icon">🔧</span>';
      stepsHtml += '<span class="agent-steps-title">工具调用 (' + m._stepData.length + ' 步)</span>';
      stepsHtml += '<span class="agent-steps-status">' + statusText + '</span>';
      stepsHtml += '</summary>';
      stepsHtml += '<div class="agent-steps-content">';
      
      for (let i = 0; i < m._stepData.length; i++) {
        const sd = m._stepData[i];
        const ok = sd.result && !sd.result.error;
        const icon = ok ? "\u2713" : "\u2715";
        let argsSummary = "";
        if (sd.args && Object.keys(sd.args).length) {
          const parts = [];
          for (const [k, v] of Object.entries(sd.args)) {
            const val = typeof v === "string" ? (v.length > 40 ? v.slice(0,40)+"\u2026" : v) : JSON.stringify(v);
            parts.push(k + "=" + val);
          }
          argsSummary = parts.join(", ");
        }
        let resultSummary = "";
        if (sd.result) {
          if (ok) {
            if (Array.isArray(sd.result.results)) resultSummary = sd.result.results.length + " 条结果";
            else if (sd.result.items) resultSummary = sd.result.items.length + " 项";
            else if (sd.result.content) resultSummary = sd.result.content.slice(0, 50);
            else if (sd.result.result !== undefined) resultSummary = String(sd.result.result);
            else if (sd.result.datetime) resultSummary = sd.result.datetime;
            else resultSummary = "成功";
          } else {
            resultSummary = sd.result.error || "失败";
          }
        }
        const resultStr = sd.result ? JSON.stringify(sd.result, null, 2) : "";
        const argsStr = sd.args && Object.keys(sd.args).length ? JSON.stringify(sd.args, null, 2) : "";

        stepsHtml += '<div class="agent-step '+(ok?'ok':'err')+'">';
        stepsHtml += '<div class="step-head">';
        stepsHtml += '<span class="step-num">'+(i+1)+'</span>';
        stepsHtml += '<span class="step-icon '+(ok?'ok':'err')+'">'+icon+'</span>';
        stepsHtml += '<span class="step-tool">'+this.escape(sd.tool)+'</span>';
        if (argsSummary) stepsHtml += '<span class="step-args">'+this.escape(argsSummary)+'</span>';
        stepsHtml += '<span class="step-result '+(ok?'ok':'err')+'">'+this.escape(resultSummary)+'</span>';
        /* 文件下载/预览链接：从工具结果中提取本地文件路径 */
        const _filePaths = this.extractFilePaths(sd);
        for (const _fp of _filePaths) {
          const _fname = _fp.split(/[\\/]/).pop();
          const _isImg = /\.(png|jpe?g|gif|webp|bmp)$/i.test(_fname);
          stepsHtml += '<a class="step-file" href="'+AGENT_API+'/api/download?path='+encodeURIComponent(_fp)+'" target="_blank" rel="noopener" title="'+this.escape(_fp)+'">📎 '+this.escape(_fname)+'</a>';
          if (_isImg) stepsHtml += '<a class="step-file" href="'+AGENT_API+'/api/raw?path='+encodeURIComponent(_fp)+'" target="_blank" rel="noopener">预览</a>';
        }
        stepsHtml += '</div>';
        if (argsStr || resultStr) {
          stepsHtml += '<details class="step-details"><summary>详情</summary>';
          if (argsStr) stepsHtml += '<div class="detail-label">参数</div><pre class="detail-pre">'+this.escape(argsStr)+'</pre>';
          if (resultStr) stepsHtml += '<div class="detail-label">结果</div><pre class="detail-pre '+(ok?'ok':'err')+'">'+this.escape(resultStr)+'</pre>';
          stepsHtml += '</details>';
        }
        stepsHtml += '</div>';
      }
      stepsHtml += '</div>';
      stepsHtml += '</details>';
    }
    // 思考过程渲染：折叠面板，默认展开
    // 思考过程按阶段（【解析输入】【信息调取】等）分组显示
    let thinkHtml = "";
    if (m._think && m._think.trim()) {
      thinkHtml = '<details class="think"><summary><span class="think-icon">🧠</span>思考过程</summary><div class="think-body">'+this.renderThink(m._think)+'</div></details>';
    }
    const isAgentMsg = (m._think && m._think.trim()) || (m._stepData && m._stepData.length > 0);
    /* 优先读消息落库的 _mode，旧数据无该字段时才按思考/工具推断，避免历史标签串味 */
    const msgMode = m._mode || (isAgentMsg ? "agent" : "normal");
    const modeTag = msgMode === "agent" ? '<span class="modetag">Agent 模式</span>' : '<span class="modetag">普通</span>';
    const stateChip = store.state.task && store.state.task.convId === store.state.currentConvId ? '<span class="statechip">'+this.escape(store.state.task.phase)+'</span>' : '';
    const asstActions = '<div class="asst-actions"><button class="ma-btn asst-copy" title="复制"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button><button class="ma-btn asst-regen" title="重新生成"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg></button></div>';
    const verifyHtml = "";  /* 验证器为纯后台自检，不渲染 UI */
    /* 空白内容处理：生成中显示动画，有思考/工具调用时不显示空提示，确实空白时显示友好提示 */
    let bubbleContent = m.content || "";
    let rawHtml = false;  // 仅内部生成的动画/空提示允许作为原始HTML，模型内容一律走renderMarkdown转义
    if (!bubbleContent.trim()) {
      const hasThink = m._think && m._think.trim();
      const hasSteps = m._stepData && m._stepData.length > 0;
      // 严格判断是否正在生成中：必须同时满足busy为true、task存在、会话匹配、且消息内容为空
      const isGenerating = store.state.busy && store.state.task && store.state.task.convId === store.state.currentConvId && !m.content;
      if (isGenerating) {
        /* 正在生成中，显示打字动画 */
        bubbleContent = '<span class="typing-dots"><span></span><span></span><span></span></span>';
        rawHtml = true;
      } else if (!hasThink && !hasSteps) {
        /* 生成完成但内容为空，显示友好提示 */
        bubbleContent = '<span style="color:#9ca3af;font-style:italic;">（回答未完成，可能是服务中断，请重新发送）</span>';
        rawHtml = true;
      }
    }
    return '<div class="msg assistant"><div class="avatar">R</div><div class="col">'+modeTag+stateChip+thinkHtml+stepsHtml+'<div class="bubble">'+(rawHtml ? bubbleContent : this.renderMarkdown(bubbleContent))+'</div>'+verifyHtml+asstActions+'</div></div>';
  },

  welcomeHTML() {
    return '<div id="welcome"><div class="wlogo">R</div><h2>你好，我是 Rui AI</h2><p>运行在你电脑上的本地智能助手。打开「AI 助手」模式，我就能像真正的智能体一样：查看和读写文件、执行命令、联网搜索、数学计算、读取剪贴板、截屏……一步步自主完成任务。危险操作会先征求你的同意。</p><div class="chips"><span class="chip">🔍 联网搜索</span><span class="chip">📄 读文件</span><span class="chip">✏️ 写文件</span><span class="chip">⌨️ 执行命令</span><span class="chip">🧮 计算</span><span class="chip">📸 截屏</span><span class="chip">🧠 多步任务</span></div></div>';
  },

  renderHeader() {
    this.updateModeButtons();
    this.els.statTotal.textContent = "⚡ " + store.state.tokens.session.toLocaleString();
    const speedEl = document.getElementById("statSpeed");
    if (speedEl) speedEl.textContent = store.state.genSpeed > 0 ? store.state.genSpeed.toFixed(1) + " tok/s" : "";
    this.els.stop.classList.toggle("show", store.state.busy);
    this.els.send.classList.toggle("hide", store.state.busy);
    if (store.state.task) {
      this.els.hint.textContent = "🧭 " + store.state.task.phase + (store.state.task.step ? " · 第 " + store.state.task.step + " 步" : "");
    } else {
      this.updateHint();
    }
  },

  updateHint() {
    this.els.hint.textContent = store.state.settings.mode === 'agent'
      ? "Agent 模式：思考 + 联网 + 工具调用配合完成任务"
      : "普通模式：对话 + 自动联网，不调用工具";
  },
  setMode(mode) {
    if (store.state.settings.mode === mode) return;
    if (store.state.busy) { alert("任务执行中，请先停止当前任务再切换模式"); return; }
    store.state.settings.mode = mode;
    store.saveSettings();
    this.updateModeButtons();
    this.updateHint();
    this.renderMessages();
  },
  updateModeButtons() {
    const isAgent = store.state.settings.mode === 'agent';
    if (this.els.modeNormal) this.els.modeNormal.classList.toggle("active", !isAgent);
    if (this.els.modeAgent) this.els.modeAgent.classList.toggle("active", isAgent);
  },

  // 深色模式初始化
  initTheme() {
    const savedTheme = localStorage.getItem('rui_theme') || 'light';
    this.applyTheme(savedTheme);
  },

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) {
      themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
      themeBtn.title = theme === 'dark' ? '切换到浅色模式' : '切换到深色模式';
    }
  },

  /* 流式更新：节流渲染（每100ms最多一次），避免频繁渲染导致卡顿 */
  _streamPending: false,
  _streamText: "",
  _lastStreamLen: 0,
  /**
   * 流式更新回答内容
   * 使用requestAnimationFrame批量更新，避免频繁DOM操作
   * @param {string} text - 当前回答内容
   */
  streamUpdate(text) {
    this._streamText = text || "";
    /* 过滤思考阶段标题：如果内容以【解析输入】【任务规划】【信息调取】【分析推理】【总结回答】等思考阶段标题开头，说明模型把思考过程输出到了content里，不更新气泡（保持三个点闪烁），只保存到liveMsg.content供后续过滤 */
    const thinkPhasePattern = /^\s*【(解析输入|任务规划|信息调取|分析推理|总结回答|完成情况|调整计划|阶段[：:][^】]*|步骤[：:][^】]*|第\d+步[^】]*|进度[：:][^】]*)】/;
    if (thinkPhasePattern.test(this._streamText)) {
      this._lastStreamLen = this._streamText.length;
      return;
    }
    /* 如果内容变化小于5个字符，跳过这次渲染（减少频繁渲染） */
    if (Math.abs(this._streamText.length - this._lastStreamLen) < 5) return;
    this._lastStreamLen = this._streamText.length;
    
    if (this._streamPending) return;
    this._streamPending = true;
    setTimeout(() => {
      this._streamPending = false;
      const bubbles = this.els.messages.querySelectorAll(".msg.assistant .bubble");
      if (bubbles.length) {
        try {
          /* 流式更新期间：始终用轻量渲染（仅基础inline+换行），不做表格/标题/列表块级渲染避免UI卡死。生成完成后全量渲染才用完整renderMarkdown */
          let t = this.escape(this._streamText);
          t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
          t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
          t = t.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
          t = t.replace(/\n/g, '<br>');
          bubbles[bubbles.length - 1].innerHTML = '<div style="white-space:normal;word-break:break-word;line-height:1.6;">' + t + '</div>';
        } catch(e) {
          bubbles[bubbles.length - 1].textContent = this._streamText;
        }
        // 使用智能滚动：只有用户没有手动滚动时才自动滚动
        this.smartScrollToBottom();
      }
      this._streamPending = false;
    });
  },
  /**
   * 流式更新思考过程
   * 如果思考过程元素不存在，全量渲染一次创建它
   * @param {string} text - 当前思考内容
   */
  streamThink(text) {
    const thinks = this.els.messages.querySelectorAll(".msg.assistant .think-body");
    if (thinks.length) {
      thinks[thinks.length - 1].textContent = text || "";
    } else if (text && text.trim()) {
      this.renderMessages();  // 还没有思考元素，全量渲染一次创建它
    }
  },
  /* 只更新顶部状态，不重渲染消息列表 */
  updateStatusOnly() {
    if (store.state.task) {
      this.els.hint.textContent = "🧭 " + store.state.task.phase + (store.state.task.step ? " · 第 " + store.state.task.step + " 步" : "");
    }
    this.els.stop.classList.toggle("show", store.state.busy);
    this.els.send.classList.toggle("hide", store.state.busy);
  },

  /* 编辑用户消息 */
  startEdit(msgEl, conv, userIdx) {
    const userMsgs = conv.messages.filter(m => m.role === "user");
    const msg = userMsgs[userIdx];
    if (!msg) return;
    const existing = msgEl.querySelector(".edit-box");
    if (existing) { existing.remove(); return; }
    const box = document.createElement("div");
    box.className = "edit-box";
    box.innerHTML = '<textarea class="edit-ta">'+this.escape(msg.content)+'</textarea><div class="edit-btns"><button class="save">保存并重新发送</button><button class="cancel">取消</button></div>';
    msgEl.querySelector(".col").appendChild(box);
    box.querySelector(".cancel").addEventListener("click", () => box.remove());
    box.querySelector(".save").addEventListener("click", () => {
      const newText = box.querySelector(".edit-ta").value.trim();
      if (!newText) return;
      msg.content = newText;
      store.saveConvs();
      /* 找到这条用户消息在 conv.messages 中的位置，截断后面的消息，重新发送 */
      const msgIdx = conv.messages.indexOf(msg);
      if (msgIdx >= 0) {
        conv.messages = conv.messages.slice(0, msgIdx + 1);
        store.saveConvs();
      }
      box.remove();
      this.renderMessages();
      /* 重新发送 */
      setTimeout(() => {
        if (store.state.settings.mode === 'agent') agentEngine.run(newText, store.state.currentConvId);
        else agentEngine.runNormal(newText, store.state.currentConvId);
      }, 100);
    });
  },

  /* 工具函数 */
  escape(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; },

  /* 解析思考过程，按【阶段标题】分段展示 */
  renderThink(text) {
    if (!text || !text.trim()) return '';
    const parts = text.split(/(?=【[^】]+】)/);
    if (parts.length <= 1) {
      return '<div class="think-phase"><div class="think-phase-content">' + this.escape(text).replace(/\n/g, '<br>') + '</div></div>';
    }
    let html = '';
    for (const part of parts) {
      if (!part.trim()) continue;
      const match = part.match(/^【([^】]+)】([\s\S]*)$/);
      if (match) {
        const title = match[1];
        const content = match[2].trim();
        html += '<div class="think-phase">';
        html += '<div class="think-phase-title">' + this.escape(title) + '</div>';
        if (content) html += '<div class="think-phase-content">' + this.escape(content).replace(/\n/g, '<br>') + '</div>';
        html += '</div>';
      } else {
        html += '<div class="think-phase"><div class="think-phase-content">' + this.escape(part).replace(/\n/g, '<br>') + '</div></div>';
      }
    }
    return html;
  },

  renderMarkdown(text) {
    if (!text) return "";
    const esc = this.escape;
    /* 完整Markdown渲染：for循环按行处理，支持表格/标题/列表/引用/代码块，不会死循环 */
    const startTime = performance.now();
    
    /* 内容过长直接返回纯文本，避免渲染卡顿 */
    if (text.length > 8000) {
      console.warn("renderMarkdown: 内容过长(" + text.length + "字符)，返回纯文本");
      return '<p>' + esc(text).replace(/\n/g, '<br>') + '</p>';
    }
    
    try {
      /* 第一步：保护代码块（包括未闭合的） */
      const codeBlocks = [];
      let html = text;
      
      /* 处理闭合的代码块 */
      html = html.replace(/```([\s\S]*?)```/g, (m, code) => {
        codeBlocks.push('<div class="code-block"><button class="code-copy" title="复制代码">复制</button><pre><code>' + esc(code.replace(/^\n/, '').replace(/\n$/, '')) + '</code></pre></div>');
        return '\x00CODE' + (codeBlocks.length - 1) + '\x00';
      });
      
      /* 处理未闭合的代码块 */
      const codeStart = html.indexOf('```');
      if (codeStart !== -1) {
        const codeContent = html.substring(codeStart + 3);
        codeBlocks.push('<div class="code-block"><button class="code-copy" title="复制代码">复制</button><pre><code>' + esc(codeContent.replace(/^\n/, '')) + '</code></pre></div>');
        html = html.substring(0, codeStart) + '\x00CODE' + (codeBlocks.length - 1) + '\x00';
      }

      /* 第二步：用for循环按行处理（绝对不会死循环） */
      const lines = html.split('\n');
      const blocks = [];
      let i = 0;
      
      for (i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        if (line.startsWith('\x00CODE')) { blocks.push(line); continue; }

        /* 标题 */
        if (/^#{1,6}\s/.test(line)) {
          const level = line.match(/^#+/) [0].length;
          const content = line.replace(/^#+\s+/, '');
          blocks.push('<h' + level + '>' + this.renderInline(esc(content)) + '</h' + level + '>');
          continue;
        }

        /* 分割线 */
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) { blocks.push('<hr>'); continue; }

        /* 引用（收集连续的引用行） */
        if (line.startsWith('>')) {
          const quoteLines = [];
          let j = i;
          while (j < lines.length && lines[j].trim().startsWith('>')) {
            quoteLines.push(lines[j].trim().replace(/^>+\s*/, ''));
            j++;
          }
          blocks.push('<blockquote>' + this.renderInline(esc(quoteLines.join(' '))) + '</blockquote>');
          i = j - 1;
          continue;
        }

        /* 表格（需要表头+分隔线） */
        if (line.startsWith('|') && line.endsWith('|') && i + 1 < lines.length) {
          const nextLine = lines[i+1].trim();
          if (nextLine.startsWith('|') && nextLine.endsWith('|') && /^[\s\-|:]+$/.test(nextLine.replace(/\|/g, ''))) {
            const tableLines = [];
            let j = i;
            while (j < lines.length) {
              const l = lines[j].trim();
              if (l.startsWith('|') && l.endsWith('|')) {
                tableLines.push(l);
                j++;
              } else break;
            }
            if (tableLines.length >= 2) {
              blocks.push(this.renderTable(tableLines.map(l => l.split('|').slice(1, -1).map(c => esc(c.trim())))));
            }
            i = j - 1;
            continue;
          }
        }

        /* 无序列表 */
        if (/^[-*+]\s+/.test(line)) {
          const items = [];
          let j = i;
          while (j < lines.length && /^[-*+]\s+/.test(lines[j].trim())) {
            items.push(this.renderInline(esc(lines[j].trim().replace(/^[-*+]\s+/, ''))));
            j++;
          }
          blocks.push('<ul>' + items.map(it => '<li>' + it + '</li>').join('') + '</ul>');
          i = j - 1;
          continue;
        }

        /* 有序列表 */
        if (/^\d+\.\s+/.test(line)) {
          const items = [];
          let j = i;
          while (j < lines.length && /^\d+\.\s+/.test(lines[j].trim())) {
            items.push(this.renderInline(esc(lines[j].trim().replace(/^\d+\.\s+/, ''))));
            j++;
          }
          blocks.push('<ol>' + items.map(it => '<li>' + it + '</li>').join('') + '</ol>');
          i = j - 1;
          continue;
        }

        /* 普通段落（收集连续的普通行） */
        const paraLines = [];
        let j = i;
        while (j < lines.length && lines[j].trim()) {
          const l = lines[j].trim();
          if (/^#{1,6}\s/.test(l) || /^[-*+]\s+/.test(l) || /^\d+\.\s+/.test(l) || l.startsWith(">") || l.startsWith("\x00CODE") || (l.startsWith("|") && l.endsWith("|")) || /^-{3,}$/.test(l) || /^\*{3,}$/.test(l) || /^_{3,}$/.test(l)) break;
          paraLines.push(l);
          j++;
        }
        if (paraLines.length) blocks.push('<p>' + this.renderInline(esc(paraLines.join(' '))) + '</p>');
        i = j - 1;
      }

      /* 第三步：恢复代码块 */
      html = blocks.join('').replace(/\x00CODE(\d+)\x00/g, (m, idx) => codeBlocks[parseInt(idx)] || '');
      const elapsed = performance.now() - startTime;
      if (elapsed > 30) {
        console.warn("renderMarkdown: 渲染耗时" + elapsed.toFixed(1) + "ms，" + lines.length + "行，" + text.length + "字符");
      }
      return html;
    } catch(e) {
      console.error("renderMarkdown error:", e);
      return '<p>' + esc(text) + '</p>';
    }
  },

  renderInline(text) {
    const codes = [];
    text = text.replace(/`([^`]+)`/g, (m, code) => {
      codes.push('<code>' + code + '</code>');
      return '\x01C' + (codes.length - 1) + '\x01';
    });
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(^|[^*])\*([^*]+?)\*/g, '$1<em>$2</em>');
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, label, href) => {
      const safeHref = String(href).trim().replace(/["'<>]/g, "");
      /* 仅允许 http/https、相对路径、锚点；javascript:/data:/vbscript: 等危险协议降级为纯文本 */
      if (/^(https?:|\/|\.|\#)/i.test(safeHref)) return '<a href="' + safeHref + '" target="_blank" rel="noopener noreferrer">' + label + '</a>';
      return m;  /* 危险/无法识别协议：原样保留markdown文本（入参已转义），避免残留半截括号 */
    });
    text = text.replace(/\x01C(\d+)\x01/g, (m, idx) => codes[parseInt(idx)]);
    return text;
  },

  renderTable(rows) {
    if (rows.length < 2) return rows.map(r => r.join(' ')).join('<br>');
    const header = rows[0];
    const body = rows.slice(2);
    let html = '<table><thead><tr>';
    for (const h of header) html += '<th>' + this.renderInline(h) + '</th>';
    html += '</tr></thead><tbody>';
    for (const row of body) {
      html += '<tr>';
      for (const cell of row) html += '<td>' + this.renderInline(cell) + '</td>';
      html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
  },
};

/* ================= 初始化 ================= */
store.loadSettings();
store.loadMemory();
store.loadConvs();
ui.init();
ui.renderMemoryList();
/* 确保初始化时页面正确渲染 */
ui.render();

/* 健康检查：同时检查 llama-server 和 agent_server */
let serviceStatus = { llama: true, agent: true };
async function checkHealth() {
  /* 检查 llama-server */
  try {
    const r = await fetch("/health", { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      serviceStatus.llama = true;
      ui.els.statusDot.classList.remove("down");
      ui.els.statusDot.title = "模型服务正常";
    } else throw new Error();
  } catch(e) {
    serviceStatus.llama = false;
    ui.els.statusDot.classList.add("down");
    ui.els.statusDot.title = "模型服务未运行";
  }
  /* 检查 agent_server */
  try {
    const r2 = await fetch(AGENT_API + "/health", { signal: AbortSignal.timeout(3000) });
    serviceStatus.agent = r2.ok;
  } catch(e) { serviceStatus.agent = false; }
  
  /* 服务异常时显示友好提示 */
  if (!serviceStatus.llama || !serviceStatus.agent) {
    let msg = "⚠️ 服务异常：";
    if (!serviceStatus.llama) msg += "模型服务(llama-server)未运行 ";
    if (!serviceStatus.agent) msg += "工具服务(agent_server)未运行 ";
    msg += "。请运行 启动RuiAI.bat 重启服务，或点击下方按钮重试。";
    if (!window._serviceErrorShown) {
      window._serviceErrorShown = true;
      const banner = document.createElement("div");
      banner.id = "serviceErrorBanner";
      banner.style.cssText = "position:fixed;top:0;left:0;right:0;background:rgba(239,68,68,.15);color:var(--danger);padding:10px 20px;z-index:9999;font-size:14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.15);backdrop-filter:blur(8px);border-bottom:1px solid rgba(239,68,68,.3);";
      banner.innerHTML = "<span>" + msg + "</span><button onclick='location.reload()' style='background:var(--danger);color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:13px;'>刷新重试</button>";
      document.body.appendChild(banner);
    }
  } else {
    const banner = document.getElementById("serviceErrorBanner");
    if (banner) banner.remove();
    window._serviceErrorShown = false;
  }
}
checkHealth();
setInterval(checkHealth, 15000);

/* 全局错误处理：网络请求失败时友好提示 */
window.addEventListener("unhandledrejection", function(e) {
  console.warn("未处理的Promise拒绝:", e.reason);
  if (e.reason && (e.reason.message === "Failed to fetch" || e.reason.name === "TypeError")) {
    if (!window._fetchErrorShown) {
      window._fetchErrorShown = true;
      setTimeout(() => { window._fetchErrorShown = false; }, 5000);
    }
  }
});

console.log("Rui AI v3 已启动（完整版）");
