import re

with open(r"D:\llama\webui\index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 找到TOOLS数组
m = re.search(r"const TOOLS = \[([\s\S]*?)\];", html)
tools_text = m.group(1)

# 要删除的工具
to_remove = ["browser_open","browser_click","browser_type","browser_press",
             "browser_get_text","browser_get_html","browser_wait","browser_scroll",
             "browser_evaluate","browser_screenshot","browser_download",
             "browser_back","browser_forward","browser_reload","browser_close",
             "stock_quote","fund_info"]

# 按工具定义分割：每个工具以 {type:"function",function:{name:"xxx" 开头
# 找到所有工具的起始位置
tool_starts = [(m.start(), m.group(1)) for m in re.finditer(r'\{type:"function",function:\{name:"([^"]+)"', tools_text)]

# 构建新的工具数组，跳过要删除的工具
new_tools = []
for i, (start, name) in enumerate(tool_starts):
    end = tool_starts[i+1][0] if i+1 < len(tool_starts) else len(tools_text)
    tool_def = tools_text[start:end].rstrip().rstrip(",")
    if name not in to_remove:
        new_tools.append(tool_def)

new_tools_text = ",\n  ".join(new_tools) + ","

# 替换
new_html = html[:m.start(1)] + new_tools_text + html[m.end(1):]

with open(r"D:\llama\webui\index.html", "w", encoding="utf-8") as f:
    f.write(new_html)

# 验证
remaining = re.findall(r'name:"([^"]+)"', new_tools_text)
print(f"删除后工具数量: {len(remaining)}")
print(f"工具列表: {remaining}")
print(f"工具定义字符数: {len(new_tools_text)}")
print(f"估算token: {len(new_tools_text)//3}")
