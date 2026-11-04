"""Hàm parse giá trị "bẩn" từ Excel về kiểu chuẩn.

Quy ước Việt Nam được ưu tiên: ngày đọc theo ngày/tháng/năm, dấu "." là phân cách
hàng nghìn và dấu "," là phân cách thập phân.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

EXCEL_EPOCH = date(1899, 12, 30)  # Excel coi 1900 là năm nhuận nên mốc thực tế là 30/12/1899
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y")
_NUMBER_RE = re.compile(r"-?\d[\d.,]*")
_THOUSANDS_DOT = re.compile(r"^-?\d{1,3}(\.\d{3})+$")
_THOUSANDS_COMMA = re.compile(r"^-?\d{1,3}(,\d{3})+$")


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def normalize_text(value) -> str:
    """Bỏ dấu tiếng Việt, chữ thường, gộp khoảng trắng: 'Đơn giá (VNĐ)' -> 'don gia'."""
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\(.*?\)", " ", text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_number(value) -> Decimal | None:
    """'1.250.000 đ' -> 1250000, '1,5' -> 1.5, '1.250,5' -> 1250.5, 850.5 -> 850.5."""
    if is_blank(value):
        return None
    if isinstance(value, bool):
        raise ValueError("không phải số")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    match = _NUMBER_RE.search(str(value).replace(" ", " ").replace(" ", ""))
    if not match:
        raise ValueError("không đọc được số")
    raw = match.group(0).rstrip(".,")

    if "." in raw and "," in raw:
        # Dấu xuất hiện sau cùng là dấu thập phân
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", "") if _THOUSANDS_COMMA.match(raw) else raw.replace(",", ".")
    elif "." in raw and _THOUSANDS_DOT.match(raw):
        raw = raw.replace(".", "")  # '95.000' theo kiểu Việt Nam là 95 nghìn

    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("không đọc được số") from exc


def parse_date(value) -> date | None:
    """Nhận datetime, date, số serial của Excel hoặc chuỗi ngày kiểu Việt Nam."""
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        result = _from_serial(value)
    else:
        text = str(value).strip()
        if text.isdigit():
            result = _from_serial(int(text))
        else:
            result = None
            for fmt in DATE_FORMATS:
                try:
                    result = datetime.strptime(text, fmt).date()
                    break
                except ValueError:
                    continue
            if result is None:
                raise ValueError("ngày không hợp lệ")

    if not 2000 <= result.year <= 2100:
        raise ValueError("năm nằm ngoài khoảng 2000-2100")
    return result


def _from_serial(serial: float) -> date:
    if not 20000 <= serial <= 80000:
        raise ValueError("số serial ngày không hợp lệ")
    return EXCEL_EPOCH + timedelta(days=int(serial))
