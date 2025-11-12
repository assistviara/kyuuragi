import pandas as pd
from datetime import timedelta
import jpholiday

# 入力CSVファイルのパス
input_path = "６年・５年度売上比較_新_ABEFH_with_date_merged.csv"

# データ読み込み
df = pd.read_csv(input_path)

# カラムA（日付）をdatetimeに変換
df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors="coerce")

# フラグカラムを追加（初期値 0）
df["祝祭日前日"] = 0
df["祝祭日"] = 0
df["振替休日"] = 0

# 各日付について判定
for i, date in enumerate(df.iloc[:, 0]):
    if pd.notna(date):
        # 振替休日か？
        name = jpholiday.is_holiday_name(date)
        if name and "振替" in name:
            df.loc[i, "振替休日"] = 1
        # 通常の祝祭日（振替以外）
        elif jpholiday.is_holiday(date):
            df.loc[i, "祝祭日"] = 1

        # 祝祭日前日判定（翌日が祝祭日 or 振替休日）
        next_name = jpholiday.is_holiday_name(date + timedelta(days=1))
        if jpholiday.is_holiday(date + timedelta(days=1)):
            df.loc[i, "祝祭日前日"] = 1


# 出力ファイルのパス
output_path = "６年・５年度売上比較_祝日フラグ付き.csv"

# 保存
df.to_csv(output_path, index=False, encoding="utf-8-sig")

output_path
