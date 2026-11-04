"""Đọc workbook bằng OpenPyXL, gỡ merged cell và tìm dòng header."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from .parsers import is_blank, normalize_text

# Tên cột chuẩn -> các cách viết đã gặp trong file thực tế (đã bỏ dấu, chữ thường)
COLUMN_ALIASES: dict[str, set[str]] = {
    "date": {"ngay", "ngay xuat", "ngay nhap", "ngay chung tu", "date"},
    "material_code": {"ma vt", "ma vat tu", "ma hang", "code"},
    "material_name": {"ten vat tu", "ten vt", "ten hang", "dien giai"},
    "unit": {"dvt", "don vi", "don vi tinh"},
    "quantity": {"so luong", "sl", "khoi luong", "kl"},
    "unit_price": {"don gia", "gia don vi"},
    "amount": {"thanh tien", "tong tien"},
}
REQUIRED_COLUMNS = {"date", "quantity", "unit_price"}
HEADER_SCAN_ROWS = 20
SITE_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(CT\d{2,})(?!\d)", re.IGNORECASE)


@dataclass
class SheetTable:
    file: str
    sheet: str
    site_code: str | None
    header_row: int  # số dòng trong Excel (bắt đầu từ 1)
    columns: dict[str, int]  # tên cột chuẩn -> vị trí cột (0-based)
    rows: list[tuple[int, tuple]] = field(default_factory=list)  # (số dòng Excel, giá trị)


def match_column(header_cell) -> str | None:
    if is_blank(header_cell):
        return None
    text = normalize_text(header_cell)
    for canonical, aliases in COLUMN_ALIASES.items():
        if text in aliases:
            return canonical
    return None


def unmerge_and_fill(ws) -> None:
    """Gỡ từng vùng merge và chép giá trị ô góc trên-trái vào mọi ô trong vùng.

    Nhờ vậy một ô "Ngày" merge dọc cho 3 dòng sẽ thành 3 dòng cùng ngày,
    thay vì 1 dòng có ngày và 2 dòng ngày trống.
    """
    for merged in list(ws.merged_cells.ranges):
        value = ws.cell(merged.min_row, merged.min_col).value
        ws.unmerge_cells(str(merged))
        for row in range(merged.min_row, merged.max_row + 1):
            for col in range(merged.min_col, merged.max_col + 1):
                ws.cell(row, col).value = value


def find_header(rows: list[tuple]) -> tuple[int, dict[str, int]] | None:
    """Chọn dòng có nhiều ô khớp tên cột nhất trong 20 dòng đầu."""
    best: tuple[int, dict[str, int]] | None = None
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping: dict[str, int] = {}
        for col, cell in enumerate(row):
            canonical = match_column(cell)
            if canonical and canonical not in mapping:
                mapping[canonical] = col
        if REQUIRED_COLUMNS <= mapping.keys() and (best is None or len(mapping) > len(best[1])):
            best = (idx, mapping)
    return best


def detect_site_code(texts: list, filename: str) -> str | None:
    for text in [*texts, filename]:
        if isinstance(text, str):
            found = SITE_CODE_RE.search(text)
            if found:
                return found.group(1).upper()
    return None


def read_workbook(path: str | Path) -> tuple[list[SheetTable], list[dict]]:
    """Trả về các bảng đọc được và danh sách vấn đề ở mức sheet (vd. không thấy header)."""
    path = Path(path)
    # data_only=True: lấy giá trị đã tính của công thức thay vì chuỗi '=SUM(...)'
    wb = load_workbook(path, data_only=True)
    tables: list[SheetTable] = []
    issues: list[dict] = []

    for ws in wb.worksheets:
        unmerge_and_fill(ws)
        rows = list(ws.iter_rows(values_only=True))
        header = find_header(rows)
        if header is None:
            issues.append({
                "file": path.name, "sheet": ws.title, "row": None, "severity": "error",
                "field": None, "value": None,
                "message": "Không tìm thấy dòng header (cần tối thiểu cột Ngày, Số lượng, Đơn giá)",
            })
            continue

        header_idx, columns = header
        texts_above = [cell for row in rows[:header_idx] for cell in row]
        table = SheetTable(
            file=path.name,
            sheet=ws.title,
            site_code=detect_site_code(texts_above, path.stem),
            header_row=header_idx + 1,
            columns=columns,
        )
        for offset, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            table.rows.append((offset, row))
        tables.append(table)

    return tables, issues
