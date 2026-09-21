import openpyxl

wb = openpyxl.load_workbook('D:\\llama\\uploads\\【全量】9.5-9.6 21-21.xlsx')
sheet = wb.active
rows = list(sheet.iter_rows(values_only=True))
total = len(rows)
mega_rows = [r for r in rows[1:] if r and isinstance(r, list) and '新款理想 MEGA' in str(r[20])]
print(f'总行数: {total}')
print(f'新款理想 MEGA 数据条数: {len(mega_rows)}')
