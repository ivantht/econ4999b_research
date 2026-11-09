import pandas as pd
from pathlib import Path

raw = Path("replication/raw")
gpr = pd.read_excel(raw / "gpr_export.xls")
print("GPR shape", gpr.shape)
print("GPR columns", list(gpr.columns)[:40])
print(gpr.head(3).to_string())
print("--- tail cols ---")
print(list(gpr.columns)[-15:])

epu = pd.read_excel(raw / "epu_all_country.xlsx", sheet_name=None)
print("EPU sheets", list(epu))
for name, df in epu.items():
    print("SHEET", name, df.shape)
    print(list(df.columns)[:30])
    print(df.head(2).to_string())
