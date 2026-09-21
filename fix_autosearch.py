with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复自动搜索判断逻辑：必须显式设置为true才开启
old = '''    const autoSearch = store.state.settings.autoSearch !== false;  // 默认关闭'''
new = '''    const autoSearch = store.state.settings.autoSearch === true;  // 默认关闭，只有设置中显式开启才搜索'''

if old in content:
    content = content.replace(old, new)
    print('✅ 自动搜索判断逻辑已修复')
else:
    print('❌ 未找到匹配')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 修复完成')
