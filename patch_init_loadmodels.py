with open(r'D:\llama\webui\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 在init函数的this.render()后面添加this.loadModels()
old = '''    store.subscribe(() => this.render());
    this.render();
  },'''
new = '''    store.subscribe(() => this.render());
    this.render();
    this.loadModels();  // 页面初始化时从后端加载模型列表，同步顶部模型名称显示
  },'''

if old in content:
    content = content.replace(old, new)
    print('✅ init函数中添加loadModels()调用')
else:
    print('❌ 未找到匹配')

with open(r'D:\llama\webui\index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 修改完成')
