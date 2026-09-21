import xlrd
from datetime import datetime, timedelta
from collections import defaultdict

# 读取 Excel 文件
wb = xlrd.open_workbook(r'D:\llama\uploads\理想_1788182477619.xlsx')
ws = wb.sheet_by_index(0)

# 跳过表头，从第 2 行开始读取
hourly_counts = defaultdict(int)

for row_idx in range(1, ws.nrows):
    # 发言时间在第 10 列（发言时间），从 0 开始计数
    time_str = ws.cell_value(row_idx, 10)
    if time_str:
        # 处理时间字符串 "2026-08-29 22:24:23"
        try:
            dt = datetime.strptime(str(time_str), "%Y-%m-%d %H:%M:%S")
            # 向下取整到小时
            hour_key = dt.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] += 1
        except:
            pass

# 转换为列表并排序
result = []
for hour_key in sorted(hourly_counts.keys()):
    result.append([hour_key.strftime("%Y-%m-%d %H:00"), hourly_counts[hour_key]])

# 打印结果
print("每小时消息数量统计：")
for row in result:
    print(f"{row[0]}: {row[1]} 条")

print(f"\n总小时数: {len(result)}")
print(f"总消息数: {sum(hourly_counts.values())}")
