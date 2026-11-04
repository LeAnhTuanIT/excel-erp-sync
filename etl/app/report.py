"""Xuất báo cáo Excel đã định dạng bằng XlsxWriter.

Gồm 4 sheet: Tong quan (tổng theo công trình + biểu đồ), Pivot (công trình x vật tư),
Du lieu sach (bảng có filter) và Van de (các dòng lỗi/cảnh báo để đối soát).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .pipeline import PipelineResult

MONEY = "#,##0"
QTY = "#,##0.###"


def export_report(result: PipelineResult, path: str | Path) -> Path:
    path = Path(path)
    clean = result.clean.copy()
    for col in ("quantity", "unit_price", "amount"):
        clean[col] = clean[col].astype(float)
    clean["date"] = pd.to_datetime(clean["date"])

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        fmt = {
            "title": wb.add_format({"bold": True, "font_size": 14}),
            "header": wb.add_format({"bold": True, "bg_color": "#1F6FD1", "font_color": "white", "border": 1,
                                     "text_wrap": True, "valign": "vcenter"}),
            "money": wb.add_format({"num_format": MONEY}),
            "qty": wb.add_format({"num_format": QTY}),
            "date": wb.add_format({"num_format": "dd/mm/yyyy"}),
            "total": wb.add_format({"bold": True, "num_format": MONEY, "top": 1}),
            "bold": wb.add_format({"bold": True}),
        }
        _summary_sheet(writer, clean, result, fmt)
        _pivot_sheet(writer, clean, fmt)
        _data_sheet(writer, clean, fmt)
        _issues_sheet(writer, result.issues, fmt)
    return path


def _summary_sheet(writer, clean: pd.DataFrame, result: PipelineResult, fmt) -> None:
    ws = writer.book.add_worksheet("Tong quan")
    ws.write("A1", "BÁO CÁO TỔNG HỢP XUẤT VẬT TƯ", fmt["title"])

    s = result.stats
    info = [
        ("Số file", s["files"]), ("Số sheet", s["sheets"]), ("Dòng hợp lệ", s["clean_rows"]),
        ("Dòng bị loại (lỗi)", s["rejected_rows"]), ("Dòng trùng đã bỏ", s["duplicate_rows"]),
        ("Dòng trống / dòng tổng bỏ qua", s["blank_rows"] + s["total_rows"]),
    ]
    for i, (label, value) in enumerate(info, start=2):
        ws.write(i, 0, label, fmt["bold"])
        ws.write(i, 1, value)

    by_site = (clean.groupby("site_code", as_index=False)
               .agg(transactions=("row_hash", "count"), total_amount=("amount", "sum"))
               .sort_values("total_amount", ascending=False))
    start = len(info) + 3
    for col, title in enumerate(["Công trình", "Số dòng", "Tổng chi phí (VNĐ)"]):
        ws.write(start, col, title, fmt["header"])
    for i, row in enumerate(by_site.itertuples(index=False), start=start + 1):
        ws.write(i, 0, row.site_code)
        ws.write_number(i, 1, row.transactions)
        ws.write_number(i, 2, row.total_amount, fmt["money"])
    last = start + len(by_site)
    ws.write(last + 1, 0, "Tổng", fmt["bold"])
    # Dùng công thức Excel thật để người nhận sửa số liệu vẫn tự cộng lại
    ws.write_formula(last + 1, 2, f"=SUM(C{start + 2}:C{last + 1})", fmt["total"],
                     float(by_site["total_amount"].sum()))  # giá trị cache cho app không tự tính lại
    ws.set_column("A:A", 30)
    ws.set_column("B:B", 12)
    ws.set_column("C:C", 22)

    if len(by_site):
        chart = writer.book.add_chart({"type": "column"})
        chart.add_series({
            "name": "Tổng chi phí",
            "categories": ["Tong quan", start + 1, 0, last, 0],
            "values": ["Tong quan", start + 1, 2, last, 2],
            "data_labels": {"value": True, "num_format": "#,##0,,\" tr\""},
        })
        chart.set_title({"name": "Chi phí vật tư theo công trình"})
        chart.set_y_axis({"num_format": "#,##0,,\" tr\""})
        chart.set_legend({"none": True})
        ws.insert_chart("E2", chart, {"x_scale": 1.3, "y_scale": 1.2})


def _pivot_sheet(writer, clean: pd.DataFrame, fmt) -> None:
    pivot = pd.pivot_table(clean, index=["material_code", "material_name"], columns="site_code",
                           values="amount", aggfunc="sum", fill_value=0, margins=True, margins_name="Tổng")
    pivot.columns.name = None
    pivot = pivot.reset_index().rename(columns={"material_code": "Mã VT", "material_name": "Tên vật tư"})
    pivot.to_excel(writer, sheet_name="Pivot", index=False, startrow=1)
    ws = writer.sheets["Pivot"]
    ws.write("A1", "Chi phí (VNĐ) theo vật tư x công trình", fmt["bold"])
    for col, name in enumerate(pivot.columns):
        ws.write(1, col, name, fmt["header"])
    ws.set_column(0, 0, 14)
    ws.set_column(1, 1, 24)
    ws.set_column(2, len(pivot.columns) - 1, 16, fmt["money"])
    # Thang màu cho phần thân pivot (không tính dòng/cột Tổng)
    last_row, last_col = len(pivot), len(pivot.columns) - 2
    if last_row > 1 and last_col >= 2:
        ws.conditional_format(2, 2, last_row, last_col, {
            "type": "3_color_scale", "min_color": "#FFFFFF", "mid_color": "#BBD5F5", "max_color": "#1F6FD1"})
    ws.freeze_panes(2, 2)


def _data_sheet(writer, clean: pd.DataFrame, fmt) -> None:
    columns = {
        "site_code": "Công trình", "date": "Ngày", "material_code": "Mã VT", "material_name": "Tên vật tư",
        "unit": "ĐVT", "quantity": "Số lượng", "unit_price": "Đơn giá", "amount": "Thành tiền",
        "source_file": "File gốc", "source_sheet": "Sheet", "source_row": "Dòng",
    }
    df = clean[list(columns)].rename(columns=columns)
    ws = writer.book.add_worksheet("Du lieu sach")
    writer.sheets["Du lieu sach"] = ws
    rows = len(df)
    data = [[None if pd.isna(v) else v for v in r] for r in df.itertuples(index=False)]
    ws.add_table(0, 0, max(rows, 1), len(columns) - 1, {
        "data": data, "style": "Table Style Medium 2",
        "columns": [{"header": h} for h in columns.values()],
    })
    ws.set_column("A:A", 11)
    ws.set_column("B:B", 12, fmt["date"])
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 24)
    ws.set_column("E:E", 8)
    ws.set_column("F:F", 11, fmt["qty"])
    ws.set_column("G:H", 14, fmt["money"])
    ws.set_column("I:I", 26)
    ws.set_column("J:K", 9)
    if rows:
        ws.conditional_format(1, 7, rows, 7, {"type": "data_bar", "bar_color": "#7FB2EE", "bar_solid": True})
    ws.freeze_panes(1, 0)


def _issues_sheet(writer, issues: pd.DataFrame, fmt) -> None:
    columns = {"severity": "Mức độ", "file": "File", "sheet": "Sheet", "row": "Dòng",
               "field": "Cột", "value": "Giá trị gốc", "message": "Mô tả"}
    df = issues[list(columns)].rename(columns=columns)
    order = {"error": 0, "warning": 1, "info": 2}
    df = df.sort_values(by="Mức độ", key=lambda s: s.map(order))
    df.to_excel(writer, sheet_name="Van de", index=False)
    ws = writer.sheets["Van de"]
    for col, name in enumerate(df.columns):
        ws.write(0, col, name, fmt["header"])
    ws.set_column("A:A", 10)
    ws.set_column("B:B", 26)
    ws.set_column("C:E", 12)
    ws.set_column("F:F", 16)
    ws.set_column("G:G", 70)
    n = len(df)
    if n:
        for value, color in (("error", "#F8D7DA"), ("warning", "#FFF3CD"), ("info", "#E2ECF9")):
            ws.conditional_format(1, 0, n, 6, {"type": "formula", "criteria": f'=$A2="{value}"',
                                               "format": writer.book.add_format({"bg_color": color})})
        ws.autofilter(0, 0, n, 6)
    ws.freeze_panes(1, 0)
