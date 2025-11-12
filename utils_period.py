# utils_period.py
import pandas as pd
import calendar, re, os
from datetime import datetime

def _resolve_sheet_name(xls_path: str, sheet_ref):
    if isinstance(sheet_ref, str):
        return sheet_ref
    if isinstance(sheet_ref, int):
        with pd.ExcelFile(xls_path) as xf:
            try:
                return xf.sheet_names[sheet_ref]
            except IndexError:
                raise ValueError(f"シート番号 {sheet_ref} が範囲外です。候補: {xf.sheet_names}")
    raise TypeError("sheet_ref は str（シート名）か int（シート番号）で指定してください。")

def _infer_year_from_path(xls_path: str) -> int | None:
    m = re.search(r"(20\d{2})", os.path.basename(xls_path))
    return int(m.group(1)) if m else None

def compute_period_end_from_book_and_sheet(xls_path: str, sheet_ref) -> pd.Timestamp:
    """
    xls_path と sheet_ref（シート名 or シート番号）からその月の末日を返す。
    対応例:
      - '4月', '2023年4月'
      - 'R5-04', 'R05.4'
      - '2022-04', '2022/04', '2022.04'
    """
    sheet_name = _resolve_sheet_name(xls_path, sheet_ref)
    s = sheet_name.replace(" ", "")

    year = None
    month = None

    # ① YYYY[-/.]MM（ゼロ埋めあり）→ 2022-04 / 2022/04 / 2022.04
    m = re.search(r"^(20\d{2})[-\/\.](1[0-2]|0[1-9])$", s)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))

    # ② YYYY[-/.]M（ゼロ埋めなし）→ 2022-4 も拾いたい場合
    if month is None:
        m2 = re.search(r"^(20\d{2})[-\/\.](1[0-2]|[1-9])$", s)
        if m2:
            year = int(m2.group(1))
            month = int(m2.group(2))

    # ③ 'YYYY年M月' / 'M月'
    if month is None:
        m3 = re.search(r"(?:(20\d{2})年)?(1[0-2]|0?[1-9])月", s)
        if m3:
            year = int(m3.group(1)) if m3.group(1) else None
            month = int(m3.group(2))

    # ④ 'R5-04' / 'R05.4'
    if month is None:
        m4 = re.search(r"[Rr](\d+)[\./\-](1[0-2]|0?[1-9])", s)
        if m4:
            reiwa = int(m4.group(1))
            year = 2018 + reiwa  # 令和1年=2019
            month = int(m4.group(2))

    if month is None:
        raise ValueError(f"シート名から月を特定できませんでした: '{sheet_name}'")

    if year is None:
        year = _infer_year_from_path(xls_path) or datetime.today().year

    last_day = calendar.monthrange(year, month)[1]
    return pd.Timestamp(year, month, last_day)
