import pandas as pd
from pathlib import Path
import re
import calendar

# 入力ファイル
in_path = Path("６年・５年度売上比較_祝日フラグ付き.csv")
df = pd.read_csv(in_path, encoding="utf-8-sig")

date_col = "日付"

def fix_date(s):
    """
    'YYYY-MM-DD' または 'YYYY/MM/DD' 前提で、存在しない日付（例: 2022-02-30）は
    その月の最終日に丸める。
    """
    if pd.isna(s):
        return pd.NaT
    s = str(s).strip()
    
    # 正規表現で年・月・日を抜き出し
    m = re.match(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$", s)
    if not m:
        # フォーマット外はとりあえず to_datetime に任せる（エラーなら NaT）
        return pd.to_datetime(s, errors="coerce")
    
    y = int(m.group(1))
    mth = int(m.group(2))
    d = int(m.group(3))
    
    # 月が範囲外なら to_datetime に任せて NaT に
    if not (1 <= mth <= 12):
        return pd.to_datetime(s, errors="coerce")
    
    last_day = calendar.monthrange(y, mth)[1]
    if d < 1:
        d = 1
    if d > last_day:
        d = last_day
    
    return pd.Timestamp(year=y, month=mth, day=d)

# 日付を修正
df[date_col] = df[date_col].map(fix_date)

# PostgreSQL 向けに ISO 形式文字列に（DATE 型にそのまま入れるなら datetime でもOK）
df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date

# 出力ファイル
out_path = Path("６年・５年度売上比較_祝日フラグ付き_dates.csv")
df.to_csv(out_path, index=False, encoding="utf-8-sig")

out_path.as_posix(), df[date_col].head().tolist()
