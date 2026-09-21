# -*- coding: utf-8 -*-
import io

p = r'D:\llama\webui\index.html'
s = io.open(p, encoding='utf-8').read()

# 在深色模式变量中添加语义颜色变量
old_dark = '''/* 深色模式 */
[data-theme="dark"] {
  --bg: #0f172a; --bg-secondary: #1e293b; --card: #1e293b; --text: #f1f5f9; --text-secondary: #cbd5e1; --muted: #64748b;
  --border: #334155; --border-light: #1e293b;
  --code-bg: #0f172a; --code-text: #e2e8f0;
  --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
  --shadow: 0 2px 8px rgba(0,0,0,.4);
  --shadow-md: 0 4px 12px rgba(0,0,0,.5);
  --shadow-lg: 0 8px 30px rgba(0,0,0,.6);
}'''

new_dark = '''/* 深色模式 */
[data-theme="dark"] {
  --bg: #0f172a; --bg-secondary: #1e293b; --card: #1e293b; --text: #f1f5f9; --text-secondary: #cbd5e1; --muted: #64748b;
  --border: #334155; --border-light: #1e293b;
  --code-bg: #0f172a; --code-text: #e2e8f0;
  --info: #60a5fa; --info-bg: rgba(96,165,250,.1);
  --success: #4ade80; --success-bg: rgba(74,222,128,.1);
  --danger: #f87171; --danger-bg: rgba(248,113,113,.1);
  --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
  --shadow: 0 2px 8px rgba(0,0,0,.4);
  --shadow-md: 0 4px 12px rgba(0,0,0,.5);
  --shadow-lg: 0 8px 30px rgba(0,0,0,.6);
}'''

if old_dark in s:
    s = s.replace(old_dark, new_dark)
    print("OK: 深色模式变量已扩展")
else:
    print("跳过: 深色模式变量未找到")

# 在浅色模式 :root 中添加语义颜色变量
old_root = '--border: #e2e8f0; --border-light: #f1f5f9; --danger: #ef4444; --green: #22c55e; --warn: #f59e0b;'
new_root = '--border: #e2e8f0; --border-light: #f1f5f9; --danger: #ef4444; --green: #22c55e; --warn: #f59e0b; --info: #3b82f6; --info-bg: rgba(59,130,246,.08); --success: #16a34a; --success-bg: rgba(34,197,94,.08);'

if old_root in s:
    s = s.replace(old_root, new_root)
    print("OK: 浅色模式变量已扩展")
else:
    print("跳过: 浅色模式变量未找到")

# 替换硬编码颜色为 CSS 变量
replacements = [
    # .conv-running
    ('color: #3b82f6; background', 'color: var(--info); background'),
    # .statechip
    ('.statechip { font-size: 11px; color: #3b82f6; background: rgba(59,130,246,.08);', '.statechip { font-size: 11px; color: var(--info); background: var(--info-bg);'),
    # .verify-line
    ('.verify-line { margin-top: 6px; font-size: 11.5px; color: #16a34a; background: rgba(34,197,94,.06);', '.verify-line { margin-top: 6px; font-size: 11.5px; color: var(--success); background: var(--success-bg);'),
    # .step-icon.ok
    ('.step-icon.ok { background: rgba(34,197,94,.15); color: #16a34a; }', '.step-icon.ok { background: var(--success-bg); color: var(--success); }'),
    # .step-icon.err
    ('.step-icon.err { background: rgba(239,68,68,.15); color: #dc2626; }', '.step-icon.err { background: var(--danger-bg); color: var(--danger); }'),
    # .step-result.ok
    ('.step-result.ok { color: #16a34a; background: rgba(34,197,94,.1); }', '.step-result.ok { color: var(--success); background: var(--success-bg); }'),
    # .step-result.err
    ('.step-result.err { color: #dc2626; background: rgba(239,68,68,.1); }', '.step-result.err { color: var(--danger); background: var(--danger-bg); }'),
    # .detail-pre.ok
    ('.detail-pre.ok { border-left: 3px solid #16a34a; }', '.detail-pre.ok { border-left: 3px solid var(--success); }'),
    # .detail-pre.err
    ('.detail-pre.err { border-left: 3px solid #dc2626; }', '.detail-pre.err { border-left: 3px solid var(--danger); }'),
]

count = 0
for old, new in replacements:
    if old in s:
        s = s.replace(old, new)
        count += 1
        print(f"OK: 替换 {old[:40]}...")

print(f"\n共替换 {count} 处硬编码颜色")

io.open(p, 'w', encoding='utf-8').write(s)
print("文件已保存")
