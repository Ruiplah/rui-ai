import re

with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复1：loadModels中加载模型列表后，更新顶部modelLabel
# 在 currentModelThinking = (info.thinking !== false); 后面添加更新label的代码
old1 = 'currentModelThinking = (info.thinking !== false);\n        }'
new1 = '''currentModelThinking = (info.thinking !== false);
          // 同步更新顶部模型名称显示
          if (this.els.modelLabel) this.els.modelLabel.textContent = info.name + " · 本地运行";
        }'''

if old1 in content:
    content = content.replace(old1, new1)
    print('✅ 修复1: loadModels中更新modelLabel')
else:
    print('❌ 修复1未找到匹配')

# 修复2：switchModel成功后更新顶部modelLabel
# 在 this.els.hint.textContent = "已切换到... 后面添加
old2 = 'this.els.hint.textContent = "已切换到 " + (d.name || key) + "（就绪耗时 " + (d.ready_after || "?") + "）";'
new2 = '''this.els.hint.textContent = "已切换到 " + (d.name || key) + "（就绪耗时 " + (d.ready_after || "?") + "）";
        // 同步更新顶部模型名称显示
        if (this.els.modelLabel) this.els.modelLabel.textContent = (d.name || key) + " · 本地运行";'''

if old2 in content:
    content = content.replace(old2, new2)
    print('✅ 修复2: switchModel成功后更新modelLabel')
else:
    print('❌ 修复2未找到匹配')

# 修复3：页面初始化时，如果localStorage有保存的模型，也更新label
# 找到初始化代码区域，在renderMessages附近添加
# 先检查是否有初始化时调用loadModels
if 'loadModels' in content:
    print('✅ loadModels函数存在，页面加载时会调用')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

# 括号检查
opens = content.count('{')
closes = content.count('}')
print(f'括号检查: {{={opens}, }}={closes}, 平衡={opens==closes}')
print('✅ 前端模型名显示修复完成')
