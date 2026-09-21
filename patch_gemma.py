"""
为 Rui AI 添加 Gemma 4 12B 模型支持
- 后端: MODELS 字典添加 gemma-4-12b，标记 thinking=False
- 前端: 根据当前模型动态设置 enable_thinking
"""
import re
import os

BACKEND = r"D:\llama\agent_server.py"
FRONTEND = r"D:\llama\webui\index.html"

# ========== 1. 修改后端 MODELS 字典 ==========
with open(BACKEND, "r", encoding="utf-8") as f:
    be = f.read()

old_models = '''MODELS = {
    "qwen3.5-9b": {
        "name": "Qwen3.5-9B (Q4_K_M)",
        "path": r"D:\\llama\\models\\Qwen_Qwen3.5-9B-Q4_K_M.gguf",
    },
    "deepseek-r1-7b": {
        "name": "DeepSeek-R1-Distill-Qwen-7B (Q4_K_M)",
        "path": r"D:\\llama\\models\\DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
    },
}'''

new_models = '''MODELS = {
    "qwen3.5-9b": {
        "name": "Qwen3.5-9B (Q4_K_M)",
        "path": r"D:\\llama\\models\\Qwen_Qwen3.5-9B-Q4_K_M.gguf",
        "thinking": True,   # Qwen3.5 支持思考模式
    },
    "deepseek-r1-7b": {
        "name": "DeepSeek-R1-Distill-Qwen-7B (Q4_K_M)",
        "path": r"D:\\llama\\models\\DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "thinking": True,   # DeepSeek R1 始终思考
    },
    "gemma-4-12b": {
        "name": "Gemma 4 12B (QAT Q4_0)",
        "path": r"D:\\llama\\models\\gemma-4-12b-it-qat-q4_0.gguf",
        "thinking": False,  # Gemma 4 带思考通道，必须关闭否则输出空白/夹杂推敲
    },
}'''

if old_models in be:
    be = be.replace(old_models, new_models)
    print("[后端] MODELS 字典已更新")
else:
    print("[后端] 警告: 未找到原始 MODELS 字典，尝试宽松匹配...")
    # 宽松匹配：在 deepseek 条目后插入 gemma
    pattern = r'(    "deepseek-r1-7b": \{\n        "name": "DeepSeek-R1-Distill-Qwen-7B \(Q4_K_M\)",\n        "path": r"D:\\llama\\models\\DeepSeek-R1-Distill-Qwen-7B-Q4_K_M\.gguf",\n    \},\n)'
    replacement = r'\1    "gemma-4-12b": {\n        "name": "Gemma 4 12B (QAT Q4_0)",\n        "path": r"D:\\llama\\models\\gemma-4-12b-it-qat-q4_0.gguf",\n        "thinking": False,\n    },\n'
    be2 = re.sub(pattern, replacement, be)
    if be2 != be:
        be = be2
        print("[后端] 宽松匹配成功，已添加 gemma-4-12b")
    else:
        print("[后端] 错误: 无法匹配 MODELS 字典，请手动检查")

# 修改 list_models 返回 thinking 字段
old_list = '''    available = {}
    for k, v in MODELS.items():
        available[k] = {"name": v["name"], "path": v["path"], "exists": os.path.isfile(v["path"])}'''
new_list = '''    available = {}
    for k, v in MODELS.items():
        available[k] = {"name": v["name"], "path": v["path"], "exists": os.path.isfile(v["path"]), "thinking": v.get("thinking", True)}'''
if old_list in be:
    be = be.replace(old_list, new_list)
    print("[后端] list_models 已添加 thinking 字段")
else:
    print("[后端] 警告: 未找到 list_models 原始代码")

with open(BACKEND, "w", encoding="utf-8") as f:
    f.write(be)
print("[后端] 保存完成")

# ========== 2. 修改前端 ==========
with open(FRONTEND, "r", encoding="utf-8") as f:
    fe = f.read()

# 2a. 添加全局变量 currentModelThinking（在 MODEL 常量附近）
# 找到 const MODEL = 那行，在后面添加
model_const_pattern = r'(const MODEL = "[^"]+";)'
if re.search(model_const_pattern, fe):
    fe = re.sub(model_const_pattern, r'\1\nlet currentModelThinking = true;  // 当前模型是否支持思考模式（Gemma 4 需关闭）', fe, count=1)
    print("[前端] 已添加 currentModelThinking 全局变量")
else:
    print("[前端] 警告: 未找到 const MODEL")

# 2b. 修改 Agent 模式的 enable_thinking:true 为动态判断
# 第1271行附近: chat_template_kwargs:{ enable_thinking:true }
old_agent_thinking = 'chat_template_kwargs:{ enable_thinking:true }'
new_agent_thinking = 'chat_template_kwargs:{ enable_thinking:currentModelThinking }'
if old_agent_thinking in fe:
    fe = fe.replace(old_agent_thinking, new_agent_thinking)
    print("[前端] Agent 模式 enable_thinking 已改为动态判断")
else:
    print("[前端] 警告: 未找到 Agent 模式 enable_thinking:true")

# 2c. 在 loadModels 中根据当前模型设置 currentModelThinking
old_loadmodels_sel = '''      const sel = this.els.modelSelect;
      sel.innerHTML = "";
      for (const [key, info] of Object.entries(d.models || {})) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = info.name + (info.exists ? "" : "（文件不存在）");
        opt.disabled = !info.exists;
        if (key === d.current || key === store.state.settings.model) opt.selected = true;
        sel.appendChild(opt);
      }'''
new_loadmodels_sel = '''      const sel = this.els.modelSelect;
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
        }
        sel.appendChild(opt);
      }'''
if old_loadmodels_sel in fe:
    fe = fe.replace(old_loadmodels_sel, new_loadmodels_sel)
    print("[前端] loadModels 已添加思考模式设置")
else:
    print("[前端] 警告: 未找到 loadModels 原始代码")

# 2d. 在 switchModel 成功后更新 currentModelThinking
old_switch_success = '''      if (d.ok) {
        store.state.settings.model = key; store.saveSettings();
        this.els.hint.textContent = "已切换到 " + (d.name || key) + "（就绪耗时 " + (d.ready_after || "?") + "）";'''
new_switch_success = '''      if (d.ok) {
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
        this.els.hint.textContent = "已切换到 " + (d.name || key) + "（就绪耗时 " + (d.ready_after || "?") + "）";'''
if old_switch_success in fe:
    fe = fe.replace(old_switch_success, new_switch_success)
    print("[前端] switchModel 成功后已更新思考模式")
else:
    print("[前端] 警告: 未找到 switchModel 成功处理代码")

with open(FRONTEND, "w", encoding="utf-8") as f:
    f.write(fe)
print("[前端] 保存完成")

print("\n========== 全部修改完成 ==========")
