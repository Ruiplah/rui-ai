# -*- coding: utf-8 -*-
"""理想.xlsx 群聊数据分析：六项指令"""
import urllib.request, json, re, os
from collections import Counter, defaultdict

def read_doc(path):
    d = json.dumps({"tool": "read_doc", "params": {"path": path}}).encode()
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8082/api/exec", data=d, headers={"Content-Type": "application/json"}), timeout=90)
    return json.loads(r.read().decode())

r = read_doc(r"C:\Users\123\Documents\理想.xlsx")
if "error" in r:
    print("ERROR:", r["error"]); raise SystemExit
content = r["content"]
lines = content.split("\n")
print("总行数(含表头):", len(lines))

header = lines[0].split("\t")
print("列数:", len(header), header)

rows = []
for ln in lines[1:]:
    ln = ln.strip()
    if not ln:
        continue
    cells = ln.split("\t")
    # 补足列数
    cells = cells + [""] * (len(header) - len(cells))
    rows.append(dict(zip(header, cells)))
print("数据行数:", len(rows))

# 保存解析后的数据供后续使用
with open(r"D:\llama\liangxiang_rows.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
print("已保存结构化数据 -> D:\\llama\\liangxiang_rows.json")
