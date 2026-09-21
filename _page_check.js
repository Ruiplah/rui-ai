
"use strict";
const MODEL = "qwen3.5-9b";
const AGENT_API = "http://127.0.0.1:8082";
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const stopBtn = document.getElementById("stop");
const thinkChk = document.getElementById("thinkChk");
const webChk = document.getElementById("webChk");
const agentChk = document.getElementById("agentChk");
const clearBtn = document.getElementById("clearBtn");
const fileInput = document.getElementById("fileInput");
const fileinfo = document.getElementById("fileinfo");
const filenameEl = document.getElementById("filename");
const filecharsEl = document.getElementById("filechars");
const statusDot = document.getElementById("statusDot");
const hint = document.getElementById("hint");

let history = [];
let loadedFiles = [];
let abortCtrl = null;
let busy = false;
const queue = [];

/* ---------- 会话 token 统计 ---------- */
let sessionTokens = parseInt(localStorage.getItem("llm_tokens_total") || "0", 10) || 0;
function updateStatTotal() {
  document.getElementById("statTotal").textContent = "⚡ " + sessionTokens.toLocaleString();
}
function addSessionTokens(n) {
  if (!n || n < 0) return;
  sessionTokens += n;
  try { localStorage.setItem("llm_tokens_total", String(sessionTokens)); } catch(e){}
  updateStatTotal();
}
updateStatTotal();

function estimateTokens(s) {
  s = String(s || "");
  let cjk = 0, other = 0;
  for (const ch of s) { ch.charCodeAt(0) > 0x2e7f ? cjk++ : other++; }
  return Math.ceil(cjk + other * 0.28);
}
function fmtSpeed(tps) {
  if (!tps || !isFinite(tps)) return "—";
  return tps.toFixed(1) + " tok/s";
}
function addTokStats(container, opts) {
  const d = document.createElement("div");
  d.className = "tokstats";
  const p = opts.prompt || 0, c = opts.completion || 0;
  d.innerHTML =
    '⚡ 本次：提示 <b>' + p.toLocaleString() + '</b> · 生成 <b>' + c.toLocaleString() + '</b> 词元' +
    (opts.speed ? ' · 速度 <b>' + fmtSpeed(opts.speed) + '</b>' : '') +
    (opts.time ? ' · 用时 ' + opts.time.toFixed(1) + 's' : '') +
    (opts.steps ? ' · ' + opts.steps + ' 步' : '') +
    ' ｜ 会话累计 <b>' + sessionTokens.toLocaleString() + '</b> 词元';
  container.appendChild(d);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return d;
}

/* ---------- 工具定义（AI 助手模式） ---------- */
const TOOLS = [
  { type: "function", function: { name: "list_dir", description: "查看电脑上指定目录下的文件和文件夹", parameters: { type: "object", properties: { path: { type: "string", description: "要查看的目录路径，例如 D:\\ 或 C:\\Users" } }, required: ["path"] } } },
  { type: "function", function: { name: "read_file", description: "读取电脑上指定文本文件的内容", parameters: { type: "object", properties: { path: { type: "string", description: "文件的完整路径" } }, required: ["path"] } } },
  { type: "function", function: { name: "write_file", description: "创建或写入文本文件（若文件已存在需用户确认覆盖）", parameters: { type: "object", properties: { path: { type: "string", description: "要写入的文件完整路径" }, content: { type: "string", description: "文件内容" } }, required: ["path", "content"] } } },
  { type: "function", function: { name: "run_command", description: "在电脑上执行 Windows 命令行命令（cmd）。用于查看系统信息、运行程序、查询状态等。禁止用于删除或修改数据的操作。", parameters: { type: "object", properties: { command: { type: "string", description: "要执行的 cmd 命令" } }, required: ["command"] } } },
  { type: "function", function: { name: "calculator", description: "数学计算器，支持加减乘除、幂、开方、三角函数、对数等（例如：(15+3)*2^4、sqrt(144)、log(100)）", parameters: { type: "object", properties: { expr: { type: "string", description: "数学表达式" } }, required: ["expr"] } } },
  { type: "function", function: { name: "file_copy", description: "复制文件或文件夹（需用户确认）", parameters: { type: "object", properties: { src: { type: "string", description: "源路径" }, dst: { type: "string", description: "目标路径" } }, required: ["src", "dst"] } } },
  { type: "function", function: { name: "file_move", description: "移动或重命名文件、文件夹（需用户确认）", parameters: { type: "object", properties: { src: { type: "string", description: "源路径" }, dst: { type: "string", description: "目标路径" } }, required: ["src", "dst"] } } },
  { type: "function", function: { name: "file_delete", description: "删除文件或文件夹，不可恢复（需用户确认）", parameters: { type: "object", properties: { path: { type: "string", description: "要删除的路径" } }, required: ["path"] } } },
  { type: "function", function: { name: "clipboard_get", description: "读取电脑剪贴板的内容", parameters: { type: "object", properties: {} } } },
  { type: "function", function: { name: "clipboard_set", description: "把内容写入电脑剪贴板", parameters: { type: "object", properties: { text: { type: "string", description: "要写入剪贴板的文本" } }, required: ["text"] } } },
  { type: "function", function: { name: "screenshot", description: "截取当前电脑屏幕并保存为图片", parameters: { type: "object", properties: { dir: { type: "string", description: "保存目录（可选，默认 D:\\llama\\screenshots）" } } } } },
  { type: "function", function: { name: "system_info", description: "获取电脑的系统信息（操作系统、CPU、内存、显卡、磁盘空间等）", parameters: { type: "object", properties: {} } } },
  { type: "function", function: { name: "web_search", description: "联网搜索最新信息，适合查天气、新闻、实时数据等", parameters: { type: "object", properties: { query: { type: "string", description: "搜索关键词" }, n: { type: "integer", description: "返回条数（1-10，默认5）" } } } } },
  { type: "function", function: { name: "fetch_url", description: "抓取指定网页的正文内容", parameters: { type: "object", properties: { url: { type: "string", description: "网页地址" } }, required: ["url"] } } }
];

const AGENT_SYSTEM = `你是运行在用户电脑上的 AI 智能助手 Rui AI，可以像专业智能体一样自主操作这台电脑完成任务。可用工具：
1. list_dir —— 查看目录内容
2. read_file —— 读取文本文件
3. write_file —— 创建/写入文本文件
4. run_command —— 执行 Windows 命令
5. calculator —— 数学计算
6. file_copy / file_move / file_delete —— 复制/移动/删除文件（会请求用户确认）
7. clipboard_get / clipboard_set —— 读取/写入剪贴板
8. screenshot —— 截取屏幕
9. system_info —— 查看系统信息
10. web_search —— 联网搜索
11. fetch_url —— 抓取网页正文

使用规则：
- 需要信息时先调用工具获取，不要凭空猜测。
- 一个任务可能需要多步调用，逐步推进直到真正完成。
- 涉及删除、覆盖、移动文件等的操作，工具会要求用户确认，你照常发起，等待确认结果即可。
- 所有工具完成后，用清晰、有条理的中文给出最终回答；若某步失败或信息不足，如实说明。
- 你的回答要直接面向用户，给出结论和必要的细节。`;

/* ---------- 设置持久化 ---------- */
function saveSettings() {
  localStorage.setItem("llm_web", webChk.checked ? "1" : "0");
  localStorage.setItem("llm_think", thinkChk.checked ? "1" : "0");
  localStorage.setItem("llm_agent", agentChk.checked ? "1" : "0");
}
function loadSettings() {
  webChk.checked = localStorage.getItem("llm_web") === "1";
  thinkChk.checked = localStorage.getItem("llm_think") === "1";
  agentChk.checked = localStorage.getItem("llm_agent") === "1";
}
loadSettings();
saveSettings();

/* ---------- 历史记录持久化 ---------- */
function saveHistory() { try { localStorage.setItem("llm_history", JSON.stringify(history)); } catch(e){} }
function loadHistory() {
  try {
    const h = JSON.parse(localStorage.getItem("llm_history") || "[]");
    if (Array.isArray(h) && h.length) { history = h; return true; }
  } catch(e){}
  return false;
}
function showWelcome(show) {
  const w = document.getElementById("welcome");
  if (w) w.style.display = show ? "" : "none";
}
if (loadHistory()) {
  showWelcome(false);
  history.forEach(m => renderMsg(m.role, m.content, false));
}

/* ---------- Markdown 渲染（安全） ---------- */
function esc(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
          .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function renderMarkdown(src) {
  src = String(src);
  let html = "";
  const parts = src.split(/```/);
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      let code = parts[i];
      let lang = "";
      const nl = code.indexOf("\n");
      if (nl > 0) { lang = code.slice(0, nl).trim(); code = code.slice(nl + 1); }
      html += '<pre><code' + (lang ? ' data-lang="'+esc(lang)+'"' : '') + '>' + esc(code.replace(/\n$/, "")) + '</code></pre>';
    } else {
      html += renderInlineBlock(parts[i]);
    }
  }
  return html;
}
function renderInlineBlock(text) {
  const lines = text.split("\n");
  let out = "";
  let listType = null;
  const flushList = () => { if (listType) { out += "</" + listType + ">"; listType = null; } };
  for (let raw of lines) {
    let line = raw;
    if (/^\s*\|.*\|\s*$/.test(line) && line.split("|").length >= 3) {
      flushList(); out += renderTable(lines, line); break;
    }
    let m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) { flushList(); const lv = m[1].length; out += `<h${lv}>${inline(m[2])}</h${lv}>`; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { flushList(); out += "<hr>"; continue; }
    if (line.trim().startsWith(">")) {
      flushList();
      out += `<blockquote>${inline(line.replace(/^\s*>\s?/, ""))}</blockquote>`;
      continue;
    }
    m = line.match(/^\s*[-*+]\s+(.*)$/);
    if (m) {
      if (listType !== "ul") { flushList(); out += "<ul>"; listType = "ul"; }
      out += `<li>${inline(m[1])}</li>`; continue;
    }
    m = line.match(/^\s*(\d+)[.)]\s+(.*)$/);
    if (m) {
      if (listType !== "ol") { flushList(); out += "<ol>"; listType = "ol"; }
      out += `<li>${inline(m[2])}</li>`; continue;
    }
    flushList();
    out += `<p>${inline(line)}</p>`;
  }
  flushList();
  return out;
}
function renderTable(lines, first) {
  let idx = lines.indexOf(first);
  const header = first;
  const sep = lines[idx + 1] || "";
  const rows = [];
  const parse = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
  rows.push(parse(header));
  if (/^\s*\|?[\s:|-]+\|?\s*$/.test(sep)) idx++;
  for (let j = idx + 1; j < lines.length; j++) {
    const l = lines[j].trim();
    if (!l.startsWith("|") || !l.endsWith("|")) break;
    rows.push(parse(l));
  }
  let h = "<table><thead><tr>";
  rows[0].forEach(c => h += "<th>" + inline(c) + "</th>");
  h += "</tr></thead><tbody>";
  for (let r = 1; r < rows.length; r++) {
    h += "<tr>";
    rows[r].forEach(c => h += "<td>" + inline(c) + "</td>");
    h += "</tr>";
  }
  h += "</tbody></table>";
  return h;
}
function inline(t) {
  let s = esc(t);
  s = s.replace(/`([^`]+)`/g, (m, c) => "<code>" + c + "</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}

/* ---------- 消息渲染 ---------- */
const USER_AV = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
const AI_AV = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/></svg>';
function renderMsg(role, content, save = true) {
  showWelcome(false);
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  const av = document.createElement("div");
  av.className = "avatar";
  av.innerHTML = role === "user" ? USER_AV : AI_AV;
  const col = document.createElement("div");
  col.className = "col";
  const bubble = document.createElement("div");
  bubble.className = "bubble md";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }
  col.appendChild(bubble);
  wrap.appendChild(av);
  wrap.appendChild(col);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { wrap, col, bubble };
}

function addStatus(text) {
  const d = document.createElement("div");
  d.className = "status";
  d.innerHTML = '<span class="spin">⏳</span> ' + esc(text);
  messagesEl.appendChild(d);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return d;
}

/* ---------- 文件上传 ---------- */
document.getElementById("attach").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async () => {
  for (const f of fileInput.files) {
    if (f.size > 1024 * 1024 * 5) { addStatus("文件过大（超过 5MB），已跳过：" + f.name); continue; }
    const text = await f.text();
    loadedFiles.push({ name: f.name, content: text });
  }
  fileInput.value = "";
  if (loadedFiles.length) {
    const total = loadedFiles.reduce((s, x) => s + x.content.length, 0);
    filenameEl.textContent = loadedFiles.map(x => x.name).join("、");
    filecharsEl.textContent = "（共 " + total.toLocaleString() + " 字）";
    fileinfo.style.display = "block";
  } else {
    fileinfo.style.display = "none";
  }
});

function buildContextSystem() {
  const parts = [];
  if (loadedFiles.length) {
    for (const f of loadedFiles) {
      parts.push("【用户上传的文件：<" + f.name + ">】\n" + f.content.slice(0, 20000));
    }
  }
  return parts.join("\n\n");
}

/* ---------- 联网搜索（普通模式） ---------- */
async function webSearch(query) {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch(AGENT_API + "/api/search?q=" + encodeURIComponent(query) + "&n=5", { signal: ctrl.signal });
    if (!r.ok) throw new Error("搜索服务返回 " + r.status);
    const data = await r.json();
    const results = data.results || [];
    if (!results.length) return { text: "", sources: [] };
    const top = results.slice(0, 3);
    const fetched = await Promise.all(top.map(async (it) => {
      try {
        const f = await fetch(AGENT_API + "/api/fetch?url=" + encodeURIComponent(it.url), { signal: ctrl.signal });
        if (!f.ok) return null;
        return await f.json();
      } catch (e) { return null; }
    }));
    const blocks = [];
    results.forEach((it, i) => {
      const body = fetched[i] && fetched[i].text ? fetched[i].text : (it.snippet || "");
      if (body) blocks.push("来源 " + (i + 1) + "：《" + (it.title || "") + "》\n网址：" + it.url + "\n内容：" + body.slice(0, 2500));
    });
    return { text: blocks.join("\n\n"), sources: results.slice(0, 5) };
  } finally {
    clearTimeout(timeout);
  }
}

function renderSources(sources) {
  if (!sources || !sources.length) return;
  const d = document.createElement("div");
  d.className = "sources";
  d.textContent = "参考来源：";
  sources.forEach((s, i) => {
    const a = document.createElement("a");
    a.href = s.url; a.target = "_blank"; a.rel = "noopener";
    a.textContent = (i + 1) + ". " + (s.title || s.url.slice(0, 40));
    d.appendChild(a);
  });
  messagesEl.appendChild(d);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ---------- 工具调用活动显示 ---------- */
const TOOL_ICONS = { list_dir: "📂", read_file: "📄", write_file: "✏️", run_command: "⌨️", calculator: "🧮", file_copy: "📋", file_move: "➡️", file_delete: "🗑️", clipboard_get: "📥", clipboard_set: "📤", screenshot: "📸", system_info: "🖥️", web_search: "🔍", fetch_url: "🌐" };
function addActivity(container, label) {
  const item = document.createElement("div");
  item.className = "act-item waiting";
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = "⏳";
  const cmd = document.createElement("span");
  cmd.className = "cmd";
  cmd.textContent = label;
  const pre = document.createElement("pre");
  pre.className = "result";
  item.appendChild(badge);
  item.appendChild(cmd);
  item.appendChild(pre);
  item.addEventListener("click", () => item.classList.toggle("open"));
  container.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { item, badge, pre };
}
function setActivity(a, cls, text) {
  a.item.className = "act-item " + cls;
  a.badge.textContent = text || (cls === "done" ? "✓" : cls === "error" ? "✗" : "⏳");
}
function activityResult(a, obj) {
  try {
    let s = JSON.stringify(obj, null, 2);
    if (s.length > 6000) s = s.slice(0, 6000) + "\n…（已截断）";
    a.pre.textContent = s;
  } catch(e) { a.pre.textContent = String(obj); }
}

/* ---------- 确认弹窗 ---------- */
function confirmDialog(command, reason) {
  return new Promise((resolve) => {
    const modal = document.getElementById("modal");
    document.getElementById("modalCmd").textContent = command;
    const desc = document.getElementById("modalDesc");
    if (reason) desc.textContent = reason;
    else desc.textContent = "AI 助手想执行下面这条命令，它可能修改、删除数据或影响系统：";
    modal.classList.add("show");
    let settled = false;
    const finish = (v) => {
      if (settled) return;
      settled = true;
      clearInterval(timer);
      modal.classList.remove("show");
      document.getElementById("modalAllow").onclick = null;
      document.getElementById("modalDeny").onclick = null;
      resolve(v);
    };
    document.getElementById("modalAllow").onclick = () => finish("allow");
    document.getElementById("modalDeny").onclick = () => finish("deny");
    const countEl = document.getElementById("modalCount");
    let left = 60;
    countEl.textContent = "60 秒内不选择将自动拒绝";
    const timer = setInterval(() => {
      left--;
      countEl.textContent = left + " 秒内不选择将自动拒绝";
      if (left <= 0) finish("timeout");
    }, 1000);
  });
}

/* ---------- 执行工具（带安全确认） ---------- */
async function execTool(name, args, act) {
  const resp = await fetch(AGENT_API + "/api/exec", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: name, params: args }),
    signal: abortCtrl.signal
  });
  if (!resp.ok) throw new Error("工具服务错误 " + resp.status);
  let result = await resp.json();
  if (result.need_confirm) {
    setActivity(act, "waiting", "⚠️");
    act.item.title = "等待用户确认";
    const cp = result.confirm_params || {};
    const showCmd = result.command || cp.path || cp.src + " → " + cp.dst || cp.command || result.reason || "";
    const decision = await confirmDialog(showCmd, result.reason);
    if (decision === "allow") {
      const cTool = result.confirm_tool || name;
      const cParams = result.confirm_params ? Object.assign({}, result.confirm_params, { confirmed: true })
                                             : { command: result.command, confirmed: true };
      const r2 = await fetch(AGENT_API + "/api/exec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: cTool, params: cParams }),
        signal: abortCtrl.signal
      });
      result = await r2.json();
    } else {
      result = { denied: true, reason: decision === "timeout" ? "确认超时，已自动拒绝" : "用户拒绝执行该操作" };
    }
  }
  return result;
}

function toolLabel(name, args) {
  const map = {
    list_dir: "查看目录 " + (args.path || ""),
    read_file: "读取文件 " + (args.path || ""),
    write_file: "写入文件 " + (args.path || ""),
    run_command: "执行命令 " + (args.command || ""),
    calculator: "计算 " + (args.expr || ""),
    file_copy: "复制 " + (args.src || "") + " → " + (args.dst || ""),
    file_move: "移动/重命名 " + (args.src || "") + " → " + (args.dst || ""),
    file_delete: "删除 " + (args.path || ""),
    clipboard_get: "读取剪贴板",
    clipboard_set: "写入剪贴板",
    screenshot: "截取屏幕",
    system_info: "查看系统信息",
    web_search: "联网搜索 " + (args.query || ""),
    fetch_url: "抓取网页 " + (args.url || "")
  };
  return (TOOL_ICONS[name] || "🔧") + " " + (map[name] || name + " " + JSON.stringify(args || {}));
}

/* ---------- AI 助手模式：多步工具循环 ---------- */
async function runAgentTask(userText, statusEl) {
  const holder = renderMsg("assistant", "", false);
  const activityBox = document.createElement("div");
  activityBox.className = "activity";
  holder.col.insertBefore(activityBox, holder.bubble);

  let msgs = history.map(m => ({ role: m.role, content: m.content }));
  msgs.push({ role: "user", content: userText });

  const ctx = buildContextSystem();
  const fullSys = AGENT_SYSTEM + (ctx ? "\n\n" + ctx : "");

  let totalPrompt = 0, totalComp = 0, stepCount = 0, lastTimings = null;

  for (let step = 0; step < 12; step++) {
    if (abortCtrl && abortCtrl.signal.aborted) throw new Error("aborted");
    statusEl.innerHTML = '<span class="spin">⏳</span> 正在执行第 ' + (step + 1) + ' 步…';
    const body = {
      model: MODEL,
      messages: [{ role: "system", content: fullSys }, ...msgs],
      tools: TOOLS,
      chat_template_kwargs: { enable_thinking: thinkChk.checked }
    };
    const resp = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abortCtrl.signal
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error("HTTP " + resp.status + (err ? "：" + err.slice(0, 200) : ""));
    }
    const data = await resp.json();
    const choice = data.choices && data.choices[0];
    if (!choice) throw new Error("模型无返回");
    const msg = choice.message || {};
    const fr = choice.finish_reason;
    stepCount++;
    if (data.usage) {
      totalPrompt += data.usage.prompt_tokens || 0;
      totalComp += data.usage.completion_tokens || 0;
    }
    if (data.timings) lastTimings = data.timings;
    statusEl.innerHTML = '<span class="spin">⏳</span> 正在执行第 ' + stepCount + ' 步…（已用 ' +
      (totalPrompt + totalComp).toLocaleString() + ' 词元）';

    if (fr === "tool_calls" && msg.tool_calls && msg.tool_calls.length) {
      for (const tc of msg.tool_calls) {
        const fn = tc.function;
        let args = {};
        try { args = JSON.parse(fn.arguments || "{}"); } catch(e) { args = { raw: fn.arguments }; }
        const act = addActivity(activityBox, toolLabel(fn.name, args));
        statusEl.innerHTML = '<span class="spin">⏳</span> 正在执行：' + esc(toolLabel(fn.name, args));
        let result;
        try {
          result = await execTool(fn.name, args, act);
          activityResult(act, result);
          if (result.denied) {
            setActivity(act, "error");
            act.item.querySelector(".cmd").textContent += "（已被用户拒绝）";
          } else if (result.error) {
            setActivity(act, "error");
          } else {
            setActivity(act, "done");
          }
        } catch (e) {
          result = { error: String(e && e.message || e) };
          activityResult(act, result);
          setActivity(act, "error");
        }
        msgs.push({ role: "assistant", content: msg.content || "", tool_calls: [tc] });
        msgs.push({ role: "tool", content: JSON.stringify(result), tool_call_id: tc.id });
      }
      continue;
    }

    const answer = (msg.content || "").trim();
    if (msg.reasoning_content) {
      const thinkEl = document.createElement("details");
      thinkEl.className = "think";
      const thinkSum = document.createElement("summary");
      thinkSum.textContent = "思考过程";
      thinkEl.appendChild(thinkSum);
      const thinkBody = document.createElement("div");
      thinkBody.textContent = msg.reasoning_content;
      thinkEl.appendChild(thinkBody);
      holder.col.insertBefore(thinkEl, activityBox.nextSibling || holder.bubble);
    }
    holder.bubble.innerHTML = renderMarkdown(answer || "（模型没有给出文字回答）");
    messagesEl.scrollTop = messagesEl.scrollHeight;
    const aggSpeed = lastTimings ? lastTimings.predicted_per_second : null;
    const aggTime = lastTimings ? (lastTimings.predicted_ms / 1000) : null;
    addTokStats(holder.col, { prompt: totalPrompt, completion: totalComp, speed: aggSpeed, time: aggTime, steps: stepCount });
    addSessionTokens(totalPrompt + totalComp);
    return answer;
  }
  holder.bubble.innerHTML = renderMarkdown("（已达到最大工具调用步数，任务可能未完全完成。你可以继续补充需求，我会接着处理。）");
  return "";
}

/* ---------- 普通模式：流式回答 ---------- */
async function runNormalTask(text, statusEl) {
  const sources = [];
  let sysContent = buildContextSystem();
  if (webChk.checked) {
    statusEl.innerHTML = '<span class="spin">⏳</span> 正在联网搜索…';
    const sw = await webSearch(text);
    if (sw.text) {
      const now = new Date().toLocaleString("zh-CN");
      sysContent += "\n\n【联网搜索结果（搜索时间：" + now + "）】\n" + sw.text + "\n\n请优先依据以上联网资料回答；资料不足或无关时，请明确说明，再结合你自己的知识回答。回答中可引用对应来源编号。";
      sources.push(...sw.sources);
    } else {
      statusEl.innerHTML = "⚠️ 联网搜索未返回结果，将直接回答。";
    }
  }
  statusEl.innerHTML = '<span class="spin">⏳</span> 正在生成…';

  const messages = [];
  if (sysContent.trim()) messages.push({ role: "system", content: sysContent.trim() });
  messages.push(...history);

  const body = {
    model: MODEL,
    messages: messages,
    stream: true,
    chat_template_kwargs: { enable_thinking: thinkChk.checked }
  };

  const holder = renderMsg("assistant", "", false);
  const thinkEl = document.createElement("details");
  thinkEl.className = "think";
  thinkEl.style.display = "none";
  const thinkSum = document.createElement("summary");
  thinkSum.textContent = "思考过程";
  thinkEl.appendChild(thinkSum);
  const thinkBody = document.createElement("div");
  thinkEl.appendChild(thinkBody);
  holder.col.insertBefore(thinkEl, holder.bubble);

  let answer = "", reasoning = "";
  const streamStart = performance.now();
  let lastTimings = null;
  const resp = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: abortCtrl.signal
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error("HTTP " + resp.status + (err ? "：" + err.slice(0, 200) : ""));
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") continue;
      try {
        const j = JSON.parse(payload);
        if (j.timings) lastTimings = j.timings;
        const delta = j.choices && j.choices[0] && j.choices[0].delta;
        if (!delta) continue;
        if (delta.reasoning_content) reasoning += delta.reasoning_content;
        if (delta.content) answer += delta.content;
      } catch (e) {}
    }
    holder.bubble.innerHTML = renderMarkdown(answer);
    if (reasoning) {
      thinkEl.style.display = "block";
      thinkBody.textContent = reasoning;
    }
    const elapsed = (performance.now() - streamStart) / 1000;
    const cur = estimateTokens(reasoning + answer);
    if (elapsed > 0.4) {
      statusEl.innerHTML = '<span class="spin">⏳</span> 正在生成… ⚡ ' +
        fmtSpeed(cur / elapsed) + ' · 已生成约 <b>' + cur.toLocaleString() + '</b> 词元';
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
  holder.bubble.innerHTML = renderMarkdown(answer);
  if (!answer && reasoning) {
    holder.bubble.textContent = "（仅输出了思考内容，未生成正式回答。可关闭“思考模式”后重试）";
  }
  renderSources(sources);
  const finalPrompt = lastTimings ? lastTimings.prompt_n : estimateTokens(JSON.stringify(messages) + sysContent);
  const finalComp = lastTimings ? lastTimings.predicted_n : estimateTokens(answer);
  const finalSpeed = lastTimings ? lastTimings.predicted_per_second : null;
  const finalTime = lastTimings ? (lastTimings.predicted_ms / 1000) : (performance.now() - streamStart) / 1000;
  addTokStats(holder.col, { prompt: finalPrompt, completion: finalComp, speed: finalSpeed, time: finalTime });
  addSessionTokens(finalPrompt + finalComp);
  return answer || "";
}

/* ---------- 发送（含队列，任务不被打断） ---------- */
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || sendBtn.disabled) return;
  inputEl.value = "";
  autoResize();

  if (busy) {
    queue.push(text);
    renderMsg("user", text);
    renderMsg("system", "当前任务正在执行中，你的这条消息已加入队列，任务完成后我会自动接着处理，不会中断正在进行的任务。");
    return;
  }

  renderMsg("user", text);
  history.push({ role: "user", content: text });
  await runTask(text);

  while (queue.length) {
    const next = queue.shift();
    renderMsg("user", next);
    history.push({ role: "user", content: next });
    await runTask(next);
  }
}

async function runTask(text) {
  busy = true;
  sendBtn.disabled = true;
  stopBtn.style.display = "inline-flex";
  abortCtrl = new AbortController();
  const statusEl = addStatus(agentChk.checked ? "AI 助手模式，正在分析任务…" : "正在准备回复…");
  try {
    const answer = agentChk.checked ? await runAgentTask(text, statusEl) : await runNormalTask(text, statusEl);
    history.push({ role: "assistant", content: answer });
    saveHistory();
    statusEl.remove();
  } catch (err) {
    statusEl.remove();
    if (err.name === "AbortError") {
      renderMsg("system", "已停止当前任务。");
    } else {
      renderMsg("system", "出错了：" + err.message + "（请确认模型服务 8080 和工具服务 8082 在运行；若刚重启过，请等模型加载完再试）");
    }
  } finally {
    busy = false;
    sendBtn.disabled = false;
    stopBtn.style.display = "none";
    abortCtrl = null;
    inputEl.focus();
  }
}

/* ---------- 服务健康监测 ---------- */
async function checkHealth() {
  try {
    const r = await fetch("/health", { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      statusDot.classList.remove("down");
      statusDot.title = "模型服务正常";
      return;
    }
    throw new Error();
  } catch (e) {
    statusDot.classList.add("down");
    statusDot.title = "模型服务未连接（稍等，守护任务会自动拉起）";
  }
}
setInterval(checkHealth, 15000);
checkHealth();

/* ---------- 事件 ---------- */
function autoResize() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
}
inputEl.addEventListener("input", autoResize);
sendBtn.addEventListener("click", sendMessage);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
stopBtn.addEventListener("click", () => { if (abortCtrl) abortCtrl.abort(); });
webChk.addEventListener("change", saveSettings);
thinkChk.addEventListener("change", saveSettings);
agentChk.addEventListener("change", () => {
  saveSettings();
  hint.textContent = agentChk.checked
    ? "AI 助手模式：我可自主调用工具完成任务（查看/读写文件、执行命令、联网搜索、计算、截屏）；涉及删除/修改等危险操作会先征求你同意"
    : "普通对话模式：纯本地运行 · 开启「联网搜索」后结合实时网络资料回答";
});
clearBtn.addEventListener("click", () => {
  history = []; loadedFiles = [];
  fileinfo.style.display = "none";
  localStorage.removeItem("llm_history");
  messagesEl.innerHTML = "";
  showWelcome(true);
});
