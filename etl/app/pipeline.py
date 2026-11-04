"""Luồng chính: đọc nhiều file Excel -> làm sạch -> DataFrame chuẩn + danh sách vấn đề."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .parsers import is_blank, normalize_text, parse_date, parse_number
from .reader import SheetTable, read_workbook

CLEAN_COLUMNS = [
    "site_code", "date", "material_code", "material_name", "unit",
    "quantity", "unit_price", "amount", "row_hash",
    "source_file", "source_sheet", "source_row",
]
ISSUE_COLUMNS = ["file", "sheet", "row", "severity", "field", "value", "message"]
AMOUNT_TOLERANCE = Decimal("1")  # lệch dưới 1 đồng coi là do làm tròn


@dataclass
class PipelineResult:
    clean: pd.DataFrame
    issues: pd.DataFrame
    stats: dict


def process_files(paths: list[str | Path]) -> PipelineResult:
    records: list[dict] = []
    issues: list[dict] = []
    stats = {"files": 0, "sheets": 0, "rows_read": 0, "blank_rows": 0, "total_rows": 0,
             "rejected_rows": 0, "duplicate_rows": 0, "clean_rows": 0}

    for path in paths:
        stats["files"] += 1
        tables, sheet_issues = read_workbook(path)
        issues.extend(sheet_issues)
        for table in tables:
            stats["sheets"] += 1
            _process_table(table, records, issues, stats)

    clean = pd.DataFrame(records, columns=CLEAN_COLUMNS)
    clean = _drop_duplicates(clean, issues, stats)
    stats["clean_rows"] = len(clean)
    return PipelineResult(clean=clean, issues=pd.DataFrame(issues, columns=ISSUE_COLUMNS), stats=stats)


def _process_table(table: SheetTable, records: list, issues: list, stats: dict) -> None:
    cols = table.columns

    def get(row: tuple, name: str):
        idx = cols.get(name)
        return row[idx] if idx is not None and idx < len(row) else None

    def issue(row_no, severity, field, value, message):
        issues.append({"file": table.file, "sheet": table.sheet, "row": row_no, "severity": severity,
                       "field": field, "value": None if value is None else str(value), "message": message})

    if table.site_code is None:
        issue(None, "error", "site_code", None,
              "Không xác định được mã công trình từ tiêu đề hoặc tên file; bỏ qua sheet")
        return

    for row_no, row in table.rows:
        stats["rows_read"] += 1
        if all(is_blank(v) for v in row):
            stats["blank_rows"] += 1
            continue
        if _is_total_row(row):
            stats["total_rows"] += 1
            continue

        errors_before = len(issues)
        record = {"site_code": table.site_code, "source_file": table.file,
                  "source_sheet": table.sheet, "source_row": row_no}

        for field, parser, required in (
            ("date", parse_date, True),
            ("quantity", parse_number, True),
            ("unit_price", parse_number, True),
            ("amount", parse_number, False),
        ):
            raw = get(row, field)
            try:
                record[field] = parser(raw)
            except ValueError as exc:
                issue(row_no, "error", field, raw, str(exc))
                continue
            if required and record[field] is None:
                issue(row_no, "error", field, raw, "thiếu giá trị bắt buộc")

        code = get(row, "material_code")
        record["material_code"] = "".join(str(code).split()).upper() if not is_blank(code) else None
        if record["material_code"] is None:
            issue(row_no, "error", "material_code", code, "thiếu mã vật tư")
        name = get(row, "material_name")
        record["material_name"] = " ".join(str(name).split()) if not is_blank(name) else None
        unit = get(row, "unit")
        record["unit"] = str(unit).strip().lower() if not is_blank(unit) else None

        qty = record.get("quantity")
        if qty is not None and qty <= 0:
            issue(row_no, "error", "quantity", qty, "số lượng phải lớn hơn 0")
        price = record.get("unit_price")
        if price is not None and price < 0:
            issue(row_no, "error", "unit_price", price, "đơn giá không được âm")

        if any(i["severity"] == "error" for i in issues[errors_before:]):
            stats["rejected_rows"] += 1
            continue

        # Đối soát thành tiền: luôn tính lại từ SL x đơn giá, ghi nhận nếu file gốc ghi khác
        expected = (qty * price).quantize(Decimal("0.01"))
        given = record.get("amount")
        if given is None:
            issue(row_no, "info", "amount", None, f"thiếu thành tiền, đã tính = {expected:,.0f}")
        elif abs(given - expected) > AMOUNT_TOLERANCE:
            issue(row_no, "warning", "amount", given,
                  f"thành tiền lệch {given - expected:,.0f} so với SL x đơn giá ({expected:,.0f}); dùng giá trị tính lại")
        record["amount"] = expected
        record["row_hash"] = _row_hash(record)
        records.append(record)


def _is_total_row(row: tuple) -> bool:
    for value in row:
        if isinstance(value, str):
            text = normalize_text(value)
            # "Tổng", "Tổng cộng", "Cộng" là dòng tổng; tránh bắt nhầm vật tư như "Cống bê tông"
            if text == "cong" or text == "tong" or text.startswith("tong "):
                return True
    return False


def _row_hash(r: dict) -> str:
    """Khóa idempotent: cùng công trình, ngày, vật tư, SL, đơn giá => cùng một giao dịch.

    Dùng để lọc trùng khi một file bị gửi lại, và ERP dựa vào đây để không ghi 2 lần.
    """
    key = "|".join([r["site_code"], r["date"].isoformat(), r["material_code"],
                    f"{r['quantity'].normalize()}", f"{r['unit_price'].normalize()}"])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _drop_duplicates(df: pd.DataFrame, issues: list, stats: dict) -> pd.DataFrame:
    if df.empty:
        return df
    dup_mask = df.duplicated("row_hash", keep="first")
    first_seen = df.drop_duplicates("row_hash").set_index("row_hash")
    for _, dup in df[dup_mask].iterrows():
        orig = first_seen.loc[dup["row_hash"]]
        issues.append({"file": dup["source_file"], "sheet": dup["source_sheet"], "row": dup["source_row"],
                       "severity": "warning", "field": None, "value": None,
                       "message": f"trùng với {orig['source_file']} / {orig['source_sheet']} dòng {orig['source_row']}; đã bỏ"})
    stats["duplicate_rows"] = int(dup_mask.sum())
    return df[~dup_mask].reset_index(drop=True)
