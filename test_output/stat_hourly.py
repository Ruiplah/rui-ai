from openpyxl import load_workbook
from datetime import datetime
from collections import defaultdict

# 读取 Excel 文件
wb = load_workbook('D:\\llama\\uploads\\理想_1788182477619.xlsx', data_only=True)
ws = wb.active

# 读取数据（跳过标题行）
hourly_counts = defaultdict(int)

for row in ws.iter_rows(min_row=2):
    # 发言时间是第 11 列（从 1 开始）
    time_cell = row[10].value
    if time_cell:
        try:
            # 解析时间字符串
            time_str = str(time_cell)
            # 尝试解析格式 "2026-08-29 22:24:23"
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            hour_key = dt.strftime("%Y-%m-%d %H:00")
            hourly_counts[hour_key] += 1
        except:
            try:
                # 尝试另一种格式
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                hour_key = dt.strftime("%Y-%m-%d %H:00")
                hourly_counts[hour_key] += 1
            except:
                pass

# 打印结果
print("每小时消息数量统计：")
for hour in sorted(hourly_counts.keys()):
    print(f"{hour}: {hourly_counts[hour]} 条")

# 保存结果到 Excel
wb_out = load_workbook('D:\\llama\\test_output\\小时统计.xlsx')
ws_out = wb_out.active
ws_out['A1'] = '小时'
ws_out['B1'] = '条数'

row_idx = 2
for hour in sorted(hourly_counts.keys()):
    ws_out[f'A{row_idx}'] = hour
    ws_out[f'B{row_idx}'] = hourly_counts[hour]
    row_idx += 1

wb_out.save('D:\\llama\\test_output\\小时统计.xlsx')
print(f"\n统计结果已保存到 D:\\llama\\test_output\\小时统计.xlsx")
