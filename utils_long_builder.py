# utils_long_builder.py
from __future__ import annotations
import re, math
import pandas as pd
from typing import List, Tuple, Union

# --- ユーティリティ（半角化/金額パース） --------------------------------
DIGITS_FW = "０１２３４５６７８９，．"
DIGITS_HW = "0123456789,."
_tbl_fw2hw = str.maketrans(DIGITS_FW, DIGITS_HW)

def to_halfwidth(s: str) -> str:
    return s.translate(_tbl_fw2hw).replace("円", "")

def parse_amount_token(text: str) -> float | None:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    s = to_halfwidth(str(text))
    s = s.replace(",", "").strip()
    neg = False
    if s.startswith(("△", "-", "▲")):
        neg = True
        s = s[1:].strip()
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None

# 「ラベル + 金額」を同一セルから抜く（フォールバック用）
RE_PAIR = re.compile(r"""
    (?P<label>[^0-9０-９△▲\-\(\)（）:：]+?)   # 数字・符号の前の短いラベル
    [\s:：]*                                   
    (?P<sign>△|▲|\()?                          
    \s*
    (?P<num>[0-9０-９][0-9０-９,，\.．]*)        
    \s*
    (?:円|\))?                                 
""", re.VERBOSE)

def extract_pairs_from_inline_remark(remark: str) -> list[tuple[str, float]]:
    if remark is None or str(remark).strip() == "":
        return []
    text = str(remark)
    pairs = []
    for m in RE_PAIR.finditer(text):
        label = m.group("label").strip()
        label = re.sub(r"[、，,／/・\s]+$", "", label)
        label = re.sub(r"^[、，,／/・\s]+", "", label)
        raw = (m.group("sign") or "") + (m.group("num") or "")
        val = parse_amount_token(raw)
        if label and val is not None:
            pairs.append((label, val))
    return pairs

# --- 備考のラベル列/金額列の自動推定 --------------------------------------
def _is_numeric_like(x) -> bool:
    if pd.isna(x): 
        return False
    return parse_amount_token(x) is not None

def pick_remark_label_and_amount_columns(df: pd.DataFrame, remark_name: str) -> tuple[pd.Series, pd.Series | None]:
    """
    同名 '備考' 列が複数ある場合：
      - 文字（非数）セルが多い列 → ラベル列
      - 数値っぽいセルが多い列 → 金額列
    片方しか無い場合は、金額列は None を返す。
    """
    idxs = [i for i, c in enumerate(df.columns) if c == remark_name]
    if not idxs:
        raise KeyError(f"備考列が見当たりません: {remark_name}")
    if len(idxs) == 1:
        return df.iloc[:, idxs[0]], None

    # 複数ある場合は役割分担
    stats = []
    for i in idxs:
        col = df.iloc[:, i]
        num_cnt = int(col.apply(_is_numeric_like).sum())
        str_cnt = int((~col.apply(_is_numeric_like)) & col.astype(str).str.strip().ne("")).sum()
        stats.append((i, num_cnt, str_cnt))
    # ラベル候補：非数（文字）多い列
    label_i = sorted(stats, key=lambda t: (t[2], -t[1]), reverse=True)[0][0]
    # 金額候補：数値多い列（ラベルと同じなら次点）
    amount_i = None
    for i, num_cnt, str_cnt in sorted(stats, key=lambda t: (t[1], -t[2]), reverse=True):
        if i != label_i and num_cnt > 0:
            amount_i = i
            break

    label_ser = df.iloc[:, label_i]
    amount_ser = df.iloc[:, amount_i] if amount_i is not None else None
    return label_ser, amount_ser

# --- メイン：ロング化 ------------------------------------------------------
def build_long_records(
    df: pd.DataFrame,
    col_account: str,
    col_remark: Union[str, list[str], pd.Series, pd.DataFrame],
) -> pd.DataFrame:
    """
    2パターン対応：
      A) 備考セル内が「ラベル + 金額」混在 → 正規表現で抽出
      B) 備考(ラベル)列 + 備考(金額)列が別 → 同名列の役割を自動推定してペア化
    返すカラム: ['account', 'remark_item', 'amount']
    """
    # 勘定科目は前方埋め（マージセル崩れ対策）
    acc = df[col_account]
    if acc.isna().any():
        acc = acc.ffill()
    acc = acc.astype(str).str.strip()

    # 備考列を Series に整える / 複数なら役割判定
    if isinstance(col_remark, str):
        # 同名の重複に対応して役割分担
        label_ser, amount_ser = pick_remark_label_and_amount_columns(df, col_remark)
    elif isinstance(col_remark, list):
        sub = df[col_remark]
        label_ser = sub.iloc[:, 0]
        amount_ser = sub.iloc[:, 1] if sub.shape[1] >= 2 else None
    elif isinstance(col_remark, pd.DataFrame):
        label_ser = col_remark.iloc[:, 0]
        amount_ser = col_remark.iloc[:, 1] if col_remark.shape[1] >= 2 else None
    elif isinstance(col_remark, pd.Series):
        label_ser, amount_ser = col_remark, None
    else:
        raise ValueError("col_remark は str / list[str] / Series / DataFrame のいずれかにしてください。")

    records = []
    # 行ごとに処理
    for a, label_cell, amt_cell in zip(acc, label_ser, amount_ser if amount_ser is not None else label_ser):
        label_text = ("" if pd.isna(label_cell) else str(label_cell)).strip()
        if not label_text:
            continue

        if amount_ser is not None:
            # パターンB：列分割型
            v = parse_amount_token(amt_cell)
            if v is not None:
                records.append({"account": a, "remark_item": label_text, "amount": v})
            else:
                # 金額列が空なら、フォールバックで備考セル内から試す
                for item, val in extract_pairs_from_inline_remark(label_text):
                    records.append({"account": a, "remark_item": item, "amount": val})
        else:
            # パターンA：備考1列にラベル+金額が混在
            pairs = extract_pairs_from_inline_remark(label_text)
            for item, val in pairs:
                records.append({"account": a, "remark_item": item, "amount": val})

    return pd.DataFrame(records, columns=["account", "remark_item", "amount"])
