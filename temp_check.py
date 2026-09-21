import openpyxl
wb = openpyxl.load_workbook(r'D:\llama\uploads\【全量】9.5-9.6 21-21.xlsx')
sheet = wb.active
rows = list(sheet.iter_rows(values_only=True))
col20_values = [str(r[20]) if r and len(r) > 20 else '' for r in rows[:50] if r]
print('专项名称列前 50 个值:')
for v in col20_values:
    print(repr(v))
