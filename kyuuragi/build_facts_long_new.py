# -*- coding: utf-8 -*-
# save as: build_simple_db_csv.py
import pandas as pd
import numpy as np
import re
import os
import calendar
from datetime import date
from pathlib import Path

EXCEL_PATH = "令和６年度月別収支状況.xlsx"   # 必要に応じてフルパスに
OUT_CSV    = "facts_long_2.csv"                # 出力先

def extract_reiwa_year_from_filename(path):
    base = os.path.basename(path)
    m = re.search(r"令和\s*([０-９0-9]+)\s*年度", base)
    if not m:
        return None
    num_str = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return 2018 + int(num_str)  # 令和1=2019

def parse_sheet_month_and_year(sheet_name, fiscal_start_year=None):
    name = str(sheet_name)
    m = re.search(r"(?<!\d)(20\d{2})[./年\-]?\s*(1[0-2]|0?[1-9])", name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"(1[0-2]|0?[1-9])\s*月", name)
    if m2 and fiscal_start_year:
        mo = int(m2.group(1))
        return (fiscal_start_year, mo) if mo>=4 else (fiscal_start_year+1, mo)
    m3 = re.fullmatch(r"\s*(1[0-2]|0?[1-9])\s*", name)
    if m3 and fiscal_start_year:
        mo = int(m3.group(1))
        return (fiscal_start_year, mo) if mo>=4 else (fiscal_start_year+1, mo)
    return None, None

def last_day_of_month(y, m):
    return calendar.monthrange(y, m)[1]

def clean_text(x):
    if pd.isna(x): return np.nan
    s = str(x).replace("\u3000", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = "".join(ch for ch in s if ch.isprintable())
    return s if s else np.nan

def main():
    # すべてのシートを header=None で読む（結合崩れ耐性）
    excel = pd.read_excel(EXCEL_PATH, sheet_name=None, header=None, dtype=object, engine="openpyxl")
    fiscal_start_year = extract_reiwa_year_from_filename(EXCEL_PATH)

    records = []
    for sheet, df in excel.items():
        # A..F のみ
        df = df.iloc[:, :6].copy()
        # ラベルを固定（列数不足でも扱えるようガード）
        cols = ['A','B','C','D','E','F'][:df.shape[1]]
        df.columns = cols
        df = df.dropna(how='all')

        # 前方埋め：A=勘定科目, E=品目（結合セル対策）
        if 'A' in df.columns:
            df['A'] = df['A'].apply(clean_text).ffill()
        if 'E' in df.columns:
            df['E'] = df['E'].apply(clean_text).ffill()

        # 金額（F）を数値化
        if 'F' in df.columns:
            ser = df['F'].astype(str)
            ser = ser.str.replace(",", "", regex=False).str.replace("¥","",regex=False).str.replace("円","",regex=False)
            ser = ser.str.replace("\u3000","",regex=False).str.replace(r"\s+","",regex=True)
            ser = ser.replace({"": np.nan})
            df['F'] = pd.to_numeric(ser, errors='coerce')
        else:
            continue  # 金額列が無いならスキップ

        # シート名から日付（末日）
        y, mo = parse_sheet_month_and_year(sheet, fiscal_start_year=fiscal_start_year)
        if y is None or mo is None:
            # 解析できないシートは無視
            continue
        d = date(y, mo, last_day_of_month(y, mo))

        # ターゲット整形
        out = pd.DataFrame({
            "日付": d,
            "勘定科目": df.get('A', np.nan),
            "品目": df.get('E', np.nan),
            "金額": df.get('F', np.nan),
        })
        # クリーニング
        out["勘定科目"] = out["勘定科目"].apply(clean_text)
        out["品目"] = out["品目"].apply(clean_text)
        # 金額欠損は除外（要件⑥）
        out = out.dropna(subset=["金額"])
        # 品目も空の場合は落とす（任意：見出し行の混入防止）
        out = out.dropna(subset=["品目"])
        records.append(out)

    if not records:
        raise RuntimeError("レコードを生成できませんでした（シート名の月解析・A/E/F列の存在を確認）。")

    result = pd.concat(records, ignore_index=True)
    # 型の明示
    result["日付"] = pd.to_datetime(result["日付"]).dt.date
    result["金額"] = result["金額"].astype(float)

    # 保存（Excel互換のため BOM 付与）
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[OK] {OUT_CSV} を出力しました。行数={len(result)}")

if __name__ == "__main__":
    main()
