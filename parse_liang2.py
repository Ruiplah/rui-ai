# -*- coding: utf-8 -*-
"""正确解析理想.xlsx（处理多行单元格），输出结构化 JSON"""
import zipfile, re, html, json

path = r"C:\Users\123\Documents\理想.xlsx"
with zipfile.ZipFile(path) as z:
    names = z.namelist()
    sst = []
    if "xl/sharedStrings.xml" in names:
        xml = z.read("xl/sharedStrings.xml").decode("utf-8")
        for si in re.findall(r"<si>.*?</si>", xml, re.S):
            ts = re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)
            sst.append("".join(html.unescape(t) for t in ts))
    sheets = sorted([n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)])
    rows_out = []
    for sh in sheets:
        xml = z.read(sh).decode("utf-8")
        for rm in re.finditer(r"<row[^>]*>(.*?)</row>", xml, re.S):
            cells = []
            for cm in re.finditer(r"<c\b[^>]*?(/?)>", rm.group(1), re.S):
                full = cm.group(0)
                if full.endswith("/>"):
                    cells.append(""); continue
                end = rm.group(1).find("</c>", cm.end())
                inner = rm.group(1)[cm.end():end]
                attrs = full
                vm = re.search(r"<v>(.*?)</v>", inner, re.S)
                t = re.search(r't="([^"]*)"', attrs)
                val = vm.group(1) if vm else ""
                if t and t.group(1) == "s" and val.isdigit() and int(val) < len(sst):
                    val = sst[int(val)]
                # 处理富文本单元格里的多个 <t>（如带换行/多段）
                if t and t.group(1) in ("s",) :
                    pass
                cells.append(html.unescape(val))
            rows_out.append(cells)

header = rows_out[0]
print("列数:", len(header), "| 总行数(含表头):", len(rows_out))
rows = []
for cells in rows_out[1:]:
    if not any(str(c).strip() for c in cells):
        continue
    cells = cells + [""] * (len(header) - len(cells))
    rows.append(dict(zip(header, cells)))
print("有效数据行数:", len(rows))

with open(r"D:\llama\liangxiang_rows.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print("已保存 -> D:\\llama\\liangxiang_rows.json")

# 快速验证
from collections import Counter
print("\n专项名称:", Counter(r.get("专项名称","") for r in rows).most_common(5))
print("群成员数:", len(set(r.get("群成员名称","") for r in rows)))
print("消息类型:", Counter(r.get("消息类型","") for r in rows).most_common(8))
