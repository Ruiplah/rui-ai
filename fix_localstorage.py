# -*- coding: utf-8 -*-
import io

p = r'D:\llama\webui\index.html'
s = io.open(p, encoding='utf-8').read()

# 替换 saveConvs 函数
old = '''  /* 持久化 */
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
  },'''

new = '''  /* 持久化：带容量保护的会话保存 */
  saveConvs() {
    try {
      localStorage.setItem("rui_convs", JSON.stringify(this.state.convs));
      localStorage.setItem("rui_cur", this.state.currentConvId);
    } catch(e) {
      console.warn("会话保存失败（localStorage已满），开始清理旧数据...");
      this._pruneConvs();
      try {
        localStorage.setItem("rui_convs", JSON.stringify(this.state.convs));
        localStorage.setItem("rui_cur", this.state.currentConvId);
        console.log("清理后保存成功");
      } catch(e2) {
        console.error("清理后仍保存失败：", e2.message);
      }
    }
  },

  /* 会话清理策略：防止 localStorage 溢出 */
  _pruneConvs() {
    // 1. 每个会话最多保留 80 条消息（超出则删除最旧的）
    for (const conv of this.state.convs) {
      if (conv.messages.length > 80) {
        conv.messages = conv.messages.slice(-80);
      }
      // 2. 工具调用步骤最多保留 5 条（减少体积）
      for (const msg of conv.messages) {
        if (msg._stepData && msg._stepData.length > 5) {
          msg._stepData = msg._stepData.slice(-5);
        }
        // 3. 工具结果内容超过 1000 字符的截断
        if (msg._stepData) {
          for (const step of msg._stepData) {
            if (step.result && typeof step.result === 'object') {
              const r = JSON.stringify(step.result);
              if (r.length > 1000) {
                step.result = { truncated: true, preview: r.substring(0, 500), note: "结果已截断" };
              }
            }
          }
        }
      }
    }
    // 4. 会话总数超过 15 个时，删除最旧的非当前会话
    if (this.state.convs.length > 15) {
      const sorted = [...this.state.convs].sort((a, b) => (a.updatedAt || 0) - (b.updatedAt || 0));
      const toDelete = sorted.slice(0, this.state.convs.length - 15);
      for (const c of toDelete) {
        if (c.id !== this.state.currentConvId) {
          this.state.convs = this.state.convs.filter(x => x.id !== c.id);
        }
      }
    }
  },'''

if old in s:
    s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8').write(s)
    print("OK: saveConvs 已更新")
else:
    print("未找到匹配内容")
