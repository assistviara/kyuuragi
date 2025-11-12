import pandas as pd
from pathlib import Path
import numpy as np

csv_path = Path("facts_long.csv")
df = pd.read_csv(csv_path, encoding="utf-8-sig")

# 推定結果（前セルの出力を再掲せず、ここで使う）
account_name_col = "勘定科目"
amount_col = "金額"
date_col = "日付"

# 1) 勘定コードが無いので、勘定名から種別を判定
income_names = {"商品売上高（4111）", "手数料収入（4112）", "その他の収入（4114）"}

# 全角・半角や空白の揺れに少し強くするための正規化関数
import re
def normalize(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    # 丸括弧/全角括弧のゆれ対策で全角括弧を丸括弧に寄せる
    s = s.replace("（", "(").replace("）", ")")
    # 全角数字→半角
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(trans)
    # 余計な連続空白を1つに
    s = re.sub(r"\s+", " ", s)
    return s

df["_acc_norm"] = df[account_name_col].map(normalize)

income_names_norm = {normalize(n) for n in income_names}

# 2) 金額を数値化（カンマ除去など）
def to_number(x):
    if pd.isna(x):
        return np.nan
    s = str(x).replace(",", "")
    try:
        return float(s)
    except:
        return np.nan

df["_amount_raw"] = df[amount_col].map(to_number)

# 3) 収入/支出フラグ
df["_is_income"] = df["_acc_norm"].isin(income_names_norm)

# 4) 収入は +abs、支出は -abs に正規化
df["金額_符号調整後"] = np.where(df["_is_income"], df["_amount_raw"].abs(), -df["_amount_raw"].abs())

# 5) 合計（全体）
total_income = df.loc[df["_is_income"], "金額_符号調整後"].sum()
total_expense = df.loc[~df["_is_income"], "金額_符号調整後"].sum()  # 既に負符号
net_profit = df["金額_符号調整後"].sum()

summary_overall = pd.DataFrame({
    "区分": ["収入(+)", "支出(-)", "当期損益(=)"],
    "金額": [total_income, total_expense, net_profit]
})

# 6) 月次集計（あれば）
monthly_summary = None
if date_col in df.columns:
    # 日付を年月(Period M)へ
    dt = pd.to_datetime(df[date_col], errors="coerce")
    ym = dt.dt.to_period("M").astype(str)
    df["_年月"] = ym
    monthly_summary = (
        df.groupby("_年月", dropna=True)["金額_符号調整後"]
        .sum()
        .reset_index()
        .rename(columns={"_年月": "年月", "金額_符号調整後": "損益合計"})
        .sort_values("年月")
    )

# 7) 出力ファイル
out_path = Path("facts_long_signed.csv")
df_out_cols = [c for c in df.columns if not c.startswith("_")]
df[df_out_cols].to_csv(out_path, index=False, encoding="utf-8-sig")

# 8) ユーザーへ可視化（プレビュー用）
from caas_jupyter_tools import display_dataframe_to_user

display_dataframe_to_user("符号調整後 明細プレビュー（先頭200行）", df[df_out_cols].head(200))
display_dataframe_to_user("損益サマリー（全体）", summary_overall)

if monthly_summary is not None:
    display_dataframe_to_user("月次損益サマリー", monthly_summary)

out_path.as_posix(), summary_overall.to_dict(orient="records")[:3], (monthly_summary.head(3).to_dict(orient="records") if monthly_summary is not None else None)


