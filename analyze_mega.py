import openpyxl
from collections import defaultdict

# 读取文件
file_path = 'D:\\llama\\uploads\\【全量】9.5-9.6 21-21.xlsx'
wb = openpyxl.load_workbook(file_path)
ws = wb.active

# 获取所有数据
all_data = list(ws.iter_rows(values_only=True))
headers = all_data[0]
data_rows = all_data[1:]

print("=" * 50)
print("列名:")
for i, h in enumerate(headers):
    print(f"  列{i}: {h}")
print("=" * 50)

# 查看前 5 行完整数据
print("\n前 5 行完整数据:")
for i, row in enumerate(data_rows[:5], 1):
    if row:
        print(f"  第{i}行: {row}")

# 查找包含 MEGA 的数据
print("\n" + "=" * 50)
print("搜索包含 MEGA 的数据:")
mega_rows = []
for row in data_rows:
    if row and len(row) > 20:
        # 检查所有列
        for j, cell in enumerate(row):
            if cell and isinstance(cell, str):
                if 'MEGA' in cell.upper():
                    print(f"  匹配到第{data_rows.index(row)+1}行，列{j}: {cell}")
                    mega_rows.append((row, j))
                    if len(mega_rows) >= 5:
                        break
        if len(mega_rows) >= 5:
            break

print(f"\n共找到 {len(mega_rows)} 条包含 MEGA 的数据")
