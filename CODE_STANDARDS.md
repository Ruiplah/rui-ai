# Rui AI 代码规范

## 1. 命名规范

### 1.1 变量和函数
- 使用 camelCase：`liveMsg`, `renderMessage`, `streamThink`
- 布尔值用 is/has/can 开头：`isAgent`, `hasThink`, `canExecute`
- 函数用动词开头：`renderMessage`, `saveConvs`, `switchConv`

### 1.2 常量
- 使用 UPPER_SNAKE_CASE：`MAX_TOKENS`, `MODEL`, `DEFAULT_MODE`
- 配置项集中定义在文件顶部

### 1.3 CSS 类名
- 使用 kebab-case：`.agent-steps`, `.think-body`, `.msg-user`
- BEM 命名：`.block__element--modifier`
- 状态类用 is- 前缀：`.is-active`, `.is-loading`

### 1.4 私有成员
- 下划线前缀：`_streamText`, `_resizeTimer`, `_modalResolve`

## 2. 注释规范

### 2.1 文件头注释
```javascript
/**
 * Rui AI - 本地智能助手前端
 * 功能：对话界面、Agent执行引擎、工具调用、流式渲染
 * 依赖：llama.cpp API (8080), agent_server (8082)
 */
```

### 2.2 函数注释（JSDoc）
```javascript
/**
 * 渲染单条消息
 * @param {Object} m - 消息对象 {role, content, _think, _stepData}
 * @returns {string} HTML字符串
 */
renderMessage(m) { ... }
```

### 2.3 复杂逻辑注释
- 说明"为什么这么做"，而不是"做了什么"
- 关键算法必须有注释
- 临时方案标记 TODO/FIXME

```javascript
// TODO: 优化为增量更新，避免全量重渲染
// FIXME: 长文本时性能较差，需要虚拟滚动
```

### 2.4 区块注释
```javascript
/* ==================== 状态管理 ==================== */
/* ==================== 渲染引擎 ==================== */
/* ==================== Agent执行引擎 ==================== */
```

## 3. 代码结构规范

### 3.1 单一职责原则
- 每个函数只做一件事
- 超过50行的函数考虑拆分
- 工具函数集中管理

### 3.2 避免嵌套过深
- 超过3层嵌套考虑提前返回
- 使用卫语句（guard clause）

```javascript
// ❌ 不推荐
if (condition1) {
  if (condition2) {
    if (condition3) {
      // 逻辑
    }
  }
}

// ✅ 推荐
if (!condition1) return;
if (!condition2) return;
if (!condition3) return;
// 逻辑
```

### 3.3 错误处理
- 所有异步操作必须有 try/catch
- 错误必须有用户友好的提示
- 关键错误必须记录日志

```javascript
try {
  await asyncOperation();
} catch (e) {
  console.error("操作失败：", e);
  showError("操作失败，请重试");
}
```

### 3.4 状态管理
- 统一通过 store 管理全局状态
- 避免直接操作 DOM 状态
- 状态变更必须通过 store 方法

## 4. 性能规范

### 4.1 防抖/节流
- 频繁触发的事件必须防抖
- 输入框、滚动事件必须节流

```javascript
// 防抖
debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
```

### 4.2 DOM 更新优化
- 使用 requestAnimationFrame 批量更新
- 避免频繁的全量重渲染
- 增量更新优先

### 4.3 内存管理
- 及时清理定时器和事件监听
- 大对象使用后置空
- 避免循环引用

## 5. 安全规范

### 5.1 XSS 防护
- 用户输入必须转义
- 使用 textContent 而非 innerHTML
- 富文本使用白名单过滤

### 5.2 命令注入防护
- 用户输入不得直接拼接到命令中
- 参数必须校验和转义
- 危险操作必须用户确认

## 6. Git 提交规范

### 6.1 提交信息格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### 6.2 Type 类型
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式
- refactor: 重构
- perf: 性能优化
- test: 测试
- chore: 构建/工具

## 7. 目录结构

```
D:\llama\
├── webui\
│   ├── index.html          # 主页面（单文件应用）
│   ├── css\                # 样式文件（待拆分）
│   └── js\                 # JS文件（待拆分）
├── agent_server.py         # 工具服务
├── 启动RuiAI.bat           # 启动脚本
├── 关闭RuiAI.bat           # 关闭脚本
└── uploads\                # 上传文件目录
```

## 8. 待优化项（TODO）

- [ ] 拆分单文件 index.html 为模块化结构
- [ ] 引入虚拟滚动优化长对话性能
- [ ] 优化思考过程流式渲染性能
- [ ] 添加单元测试
- [ ] 完善错误处理和用户提示
- [ ] 优化移动端适配
- [ ] 添加国际化支持
