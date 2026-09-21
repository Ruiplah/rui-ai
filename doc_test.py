# -*- coding: utf-8 -*-
import json, urllib.request, os

def post(tool, params):
    d = json.dumps({"tool": tool, "params": params}).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d,
        headers={"Content-Type": "application/json"}), timeout=60)
    return json.loads(r.read().decode("utf-8"))

base = "D:\\llama\\docs_test"
os.makedirs(base, exist_ok=True)

print("== 1. 创建 docx ==")
print(post("create_doc", {"path": base + "\\工作报告.docx", "content": "Rui AI 工作报告\n\n一、本月完成\n1. 完成本地模型部署\n2. 实现 AI 助手能力\n\n二、下月计划\n- 接入更多工具"}))
print("== 2. 读取 docx ==")
print(post("read_doc", {"path": base + "\\工作报告.docx"}))

print("== 3. 创建 xlsx（TSV 行） ==")
print(post("create_doc", {"path": base + "\\数据表.xlsx", "content": "姓名\t城市\t年龄\n张三\t广州\t28\n李四\t深圳\t32"}))
print("== 4. 读取 xlsx ==")
print(post("read_doc", {"path": base + "\\数据表.xlsx"}))

print("== 5. 创建 pdf ==")
print(post("create_doc", {"path": base + "\\说明.pdf", "content": "Rui AI Document\nHello World"}))
print("== 6. 读取 pdf ==")
print(post("read_doc", {"path": base + "\\说明.pdf"}))

print("== 7. 创建 md ==")
print(post("create_doc", {"path": base + "\\notes.md", "content": "# 标题\n\n正文内容"}))
print("== 8. 覆盖确认 ==")
print(post("create_doc", {"path": base + "\\notes.md", "content": "新内容"}))

# 文件大小验证
for f in ["工作报告.docx", "数据表.xlsx", "说明.pdf"]:
    p = base + "\\" + f
    print(f, os.path.getsize(p), "bytes")
