# save as: merge_facts_long.py
import pandas as pd

FILE1 = "facts_long_2.csv"
FILE2 = "facts_long_1113.csv"
OUT   = "facts_long_merged.csv"

def main():
    df1 = pd.read_csv(FILE1)
    df2 = pd.read_csv(FILE2)

    merged = pd.concat([df1, df2], ignore_index=True)

    # 日付カラム（先頭列を想定）
    date_col = merged.columns[0]
    merged[date_col] = pd.to_datetime(merged[date_col])

    # 日付の古い順にソート
    merged = merged.sort_values(date_col)

    # A,B,C,D に相当する先頭4カラムで重複を削除
    key_cols = list(merged.columns[:4])  # ["日付", "勘定科目", "品目", "金額"] のはず
    merged = merged.drop_duplicates(subset=key_cols, keep="first")

    merged.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"[OK] {OUT} を出力しました。行数={len(merged)}")

if __name__ == "__main__":
    main()
