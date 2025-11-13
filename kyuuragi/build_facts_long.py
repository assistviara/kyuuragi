# -*- coding: utf-8 -*-
"""
月次シート（例: 2022-04）の表から、
  period_end, account, remark_item, amount
のロング形式CSV (facts_long.csv) を生成するスクリプト。

前提:
- utils_period.py に compute_period_end_from_book_and_sheet があること
- utils_long_builder.py に build_long_records / pick_remark_label_and_amount_columns / parse_amount_token があること
  （重複「備考」列の “ラベル列＋金額列” 自動判定ロジック込み）
"""

import re
import pandas as pd
from pathlib import Path
import unicodedata

from utils_period import compute_period_end_from_book_and_sheet
from utils_long_builder import (
    build_long_records,
    pick_remark_label_and_amount_columns,
    parse_amount_token,
)

# ================= 設定 =================
EXCEL_PATH = "令和５年度月別収支状況.xlsx"   # 実ファイル名に合わせて
SHEET_NAME = "2022-04"                       # 例：対象シート名（末日=period_endに使う）

# ================= ユーティリティ =================
def _norm_space(s: str) -> str:
    """全角/半角スペース等を除去し、列名のゆらぎを吸収する"""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"[\s\u3000\u2000-\u200B]+", "", s)

def load_table_with_header_detection(path: str | Path, sheet_name=0) -> pd.DataFrame:
    """
    シート全体を header=None で読み、上部から「勘定科目」「備考/摘要/内訳」を含む行を
    見出し行として自動検出。以降を本表として DataFrame を返す。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {p.resolve()}")

    raw = pd.read_excel(p, sheet_name=sheet_name, header=None, engine="openpyxl")

    want_cols = ["勘定科目", "備考", "摘要", "内訳", "勘　定　科　目", "備　　　　　　　　考"]
    header_row_idx = None
    for i in range(min(len(raw), 150)):
        row_vals = [_norm_space(v) for v in raw.iloc[i].tolist()]
        hit = sum(any(_norm_space(w) in rv for rv in row_vals) for w in want_cols)
        if hit >= 2:
            header_row_idx = i
            break

    if header_row_idx is None:
        # デバッグ支援：上部プレビュー
        raise ValueError(
            "見出し行を検出できませんでした。上部プレビュー:\n"
            + raw.iloc[:60, :12].to_string(index=True)
        )

    header = raw.iloc[header_row_idx].tolist()
    df = raw.iloc[header_row_idx + 1:].copy()
    df.columns = header
    # 欠損カラム名 "Unnamed: n" を前方埋め（同じ見出しセルが横に分割されている場合の対策）
    df.columns = pd.Series(df.columns).ffill().tolist()
    # 全空行は削除
    df = df.dropna(how="all").reset_index(drop=True)
    return df

def autodetect_col(df: pd.DataFrame, cand_account: list[str], cand_remark: list[str]) -> tuple[str, str]:
    """
    列名の候補（全角空白含む表記揺れを考慮）から、実列名（df.columns中の“見た目の列名”）を返す。
    """
    norm_map = {col: _norm_space(col) for col in df.columns}

    def _find(cands: list[str]) -> str | None:
        cands_norm = [_norm_space(x) for x in cands]
        # 完全一致（正規化後）
        for real, normed in norm_map.items():
            if normed in cands_norm:
                return real
        # 部分一致（例: 勘定科目名 / 備考（内訳）など）
        for real, normed in norm_map.items():
            if any(cn and cn in normed for cn in cands_norm):
                return real
        return None

    a = _find(cand_account)
    b = _find(cand_remark)
    if not a or not b:
        missing = []
        if not a: missing.append("勘定科目")
        if not b: missing.append("備考")
        raise ValueError(f"列が見つかりませんでした: {', '.join(missing)}\n実列: {list(df.columns)}")
    return a, b

def ensure_period_end_column(df: pd.DataFrame, period_end) -> pd.DataFrame:
    """
    period_end（Timestamp/str）を固定値で列に付与（既存なら上書きしない）
    """
    if df is None:
        raise ValueError("facts_long が None です。build_long_records の戻り値をご確認ください。")
    if "period_end" in df.columns:
        return df
    out = df.copy()
    out["period_end"] = pd.to_datetime(period_end)
    return out

# ================= メイン =================
def main():
    # 1) 表読み込み（上部帯・飾り行の自動スキップ）
    df = load_table_with_header_detection(EXCEL_PATH, sheet_name=SHEET_NAME)

    # 2) シート名からその月の末日を推定（utils_period）
    period_end = compute_period_end_from_book_and_sheet(EXCEL_PATH, SHEET_NAME)

    # 3) 勘定科目・備考の列を自動検出（見出しゆらぎ対応）
    COL_CAND_ACCOUNT = ["勘定科目", "勘　定　科　目", "科目", "項目名", "account"]
    COL_CAND_REMARK  = ["備考", "備　　　　　　　　考", "摘要", "内訳", "remark"]

    col_account, col_remark = autodetect_col(df, COL_CAND_ACCOUNT, COL_CAND_REMARK)

    # --- デバッグ出力（任意） ---
    dups = [c for c in df.columns if list(df.columns).count(c) > 1]
    print("[DEBUG] duplicated headers:", dups)
    print("[DEBUG] columns:", list(df.columns))
    print("[DEBUG] col_account:", col_account, "/ col_remark:", col_remark)

    # ラベル/金額の候補を確認（同名「備考」列が複数ある場合の役割推定）
    try:
        lbl_ser, amt_ser = pick_remark_label_and_amount_columns(df, col_remark)
        print("[DEBUG] label samples:", lbl_ser.dropna().astype(str).head(5).tolist())
        if amt_ser is not None:
            print("[DEBUG] amount samples:", [parse_amount_token(x) for x in amt_ser.head(5).tolist()])
        else:
            print("[DEBUG] amount column: <inline or not provided>")
    except Exception as e:
        print("[WARN] 備考列の役割推定に失敗:", e)

    # 4) ロング化（ラベル＋金額の2列型 / 1列に混在型 の両対応）
    facts_long = build_long_records(df, col_account, col_remark)

    if facts_long.empty:
        print("[WARN] 備考から (品目, 金額) を抽出できませんでした。表の体裁（品目列・金額列の有無）をご確認ください。")
    else:
        # 5) 期末日を列付与し、保存
        facts_long = ensure_period_end_column(facts_long, period_end)
        facts_long = facts_long[["period_end", "account", "remark_item", "amount"]].copy()
        # 日付は YYYY-MM-DD で統一
        facts_long["period_end"] = pd.to_datetime(facts_long["period_end"]).dt.strftime("%Y-%m-%d")
        facts_long.sort_values(["period_end", "account", "remark_item"], inplace=True)
        facts_long.to_csv("facts_long_1113.csv", index=False, encoding="utf-8-sig")
        print("[OK] facts_long.csv を出力しました。")
        print(facts_long.head(10).to_string(index=False))

if __name__ == "__main__":
    main()
