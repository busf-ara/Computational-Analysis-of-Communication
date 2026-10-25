import pandas as pd

df = pd.read_excel("sample_5k_translated.xlsx", sheet_name="Sheet1")

# Turn NaN into null and dates into ISO strings
df = df.astype(object).where(df.notna(), None)

df.to_json("TRANSLATED_PARAGRAPHS.json", orient="records", indent=2, date_format="iso", force_ascii=False)