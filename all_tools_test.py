# -*- coding: utf-8 -*-
"""Rui AI 全部底层工具一次性回归测试"""
import urllib.request, json, os, time, traceback

BASE = "http://127.0.0.1:8082/api/exec"

def exec_tool(name, params, timeout=60):
    d = json.dumps({"tool": name, "params": params}).encode()
    req = urllib.request.Request(BASE, data=d, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        j = json.loads(r.read().decode())
        return {"ok": True, "ms": int((time.time()-t0)*1000), "data": j}
    except Exception as e:
        return {"ok": False, "ms": int((time.time()-t0)*1000), "err": str(e)[:200]}

results = []
def report(name, r, check=None):
    status = "✅" if r["ok"] else "❌"
    detail = ""
    if r["ok"]:
        d = r["data"]
        if d.get("error"):
            status = "❌"; detail = " | error: " + str(d["error"])[:120]
        elif check and not check(d):
            status = "⚠️"; detail = " | 返回异常"
    results.append((name, status, r["ms"]))
    print(f"{status} {name}  ({r['ms']}ms){detail}")

# 1. 读文件
report("read_file(txt)", exec_tool("read_file", {"path": r"D:\llama\webui\index.html"}), lambda d: "html" in d.get("content","").lower() or d.get("chars",0)>0)
# 2. 写文件
report("write_file", exec_tool("write_file", {"path": r"D:\llama\test_output\hello.txt", "content": "Rui AI 测试写入\n第二行"}))
report("read_back(write)", exec_tool("read_file", {"path": r"D:\llama\test_output\hello.txt"}), lambda d: "Rui AI 测试写入" in d.get("content",""))
# 3. 创建 docx
report("create_docx", exec_tool("create_doc", {"path": r"D:\llama\test_output\测试文档.docx", "content": "标题：季度总结\n第一条\n第二条"}))
report("read_docx", exec_tool("read_doc", {"path": r"D:\llama\test_output\测试文档.docx"}), lambda d: "季度总结" in d.get("content",""))
# 4. 创建 xlsx
report("create_xlsx", exec_tool("create_doc", {"path": r"D:\llama\test_output\报价单.xlsx", "content": "产品\t单价\t数量\n鼠标\t99\t10\n键盘\t199\t5"}))
report("read_xlsx", exec_tool("read_doc", {"path": r"D:\llama\test_output\报价单.xlsx"}), lambda d: "鼠标" in d.get("content",""))
# 5. 创建 pdf
report("create_pdf", exec_tool("create_doc", {"path": r"D:\llama\test_output\readme.pdf", "content": "Rui AI Test PDF"}))
report("read_pdf", exec_tool("read_doc", {"path": r"D:\llama\test_output\readme.pdf"}), lambda d: "Test PDF" in d.get("content",""))
# 6. stat_data
report("stat_data", exec_tool("stat_data", {"path": r"D:\llama\test_output\报价单.xlsx", "group_by": "hour"}), lambda d: "ok" in d)
# 7. calculator
report("calculator", exec_tool("calculator", {"expr": "(15+3)*2^4"}))
# 8. get_time
report("get_time", exec_tool("get_time", {}))
# 9. stock_quote
report("stock_quote", exec_tool("stock_quote", {"code": "600519"}), lambda d: d.get("name") or d.get("price"))
# 10. fund_info
report("fund_info", exec_tool("fund_info", {"code": "000834"}), lambda d: "净值" in json.dumps(d, ensure_ascii=False) or d.get("name"))
# 11. system_info
report("system_info", exec_tool("system_info", {}), lambda d: len(json.dumps(d, ensure_ascii=False)) > 20)
# 12. screenshot
report("screenshot", exec_tool("screenshot", {}), lambda d: d.get("path"))
# 13. image_info (用截屏文件)
scr = None
r = exec_tool("screenshot", {})
if r["ok"] and r["data"].get("path"):
    scr = r["data"]["path"]
    report("image_info", exec_tool("image_info", {"path": scr}), lambda d: d.get("width"))
# 14. clipboard
report("clipboard_set", exec_tool("clipboard_set", {"text": "RuiAI剪贴板测试"}))
report("clipboard_get", exec_tool("clipboard_get", {}), lambda d: "RuiAI" in json.dumps(d, ensure_ascii=False))
# 15. run_command (安全命令)
report("run_command", exec_tool("run_command", {"command": "echo RuiAI-CMD-OK"}), lambda d: "RuiAI-CMD-OK" in json.dumps(d, ensure_ascii=False))
# 16. list_dir
report("list_dir", exec_tool("list_dir", {"path": r"D:\llama"}), lambda d: d.get("count",0) > 0)
# 17. web_search
report("web_search", exec_tool("web_search", {"query": "今日广州天气", "n": 3}), lambda d: len(d.get("results", [])) > 0 or "results" in d)
# 18. fetch_url
report("fetch_url", exec_tool("fetch_url", {"url": "https://example.com"}), lambda d: "Example" in json.dumps(d, ensure_ascii=False) or "Example" in d.get("text",""))
# 19. save_memory + 读取记忆
report("save_memory", exec_tool("save_memory", {"content": "测试记忆条目"}))
# 20. ocr_image
if scr:
    report("ocr_image", exec_tool("ocr_image", {"path": scr}), lambda d: True)  # 截屏可能没文字，只要不报错

print("\n===== 汇总 =====")
ok = sum(1 for _, s, _ in results if s == "✅")
warn = sum(1 for _, s, _ in results if s == "⚠️")
fail = sum(1 for _, s, _ in results if s == "❌")
print(f"通过 {ok} / 警告 {warn} / 失败 {fail} / 共 {len(results)}")
for name, s, ms in results:
    print(f"  {s} {name} ({ms}ms)")
