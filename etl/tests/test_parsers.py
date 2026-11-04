from datetime import date, datetime
from decimal import Decimal

import pytest

from app.parsers import normalize_text, parse_date, parse_number


@pytest.mark.parametrize("raw, expected", [
    ("1.250.000 đ", Decimal("1250000")),
    ("95.000", Decimal("95000")),
    ("1,5", Decimal("1.5")),
    ("1.250,5", Decimal("1250.5")),
    ("1,250,000", Decimal("1250000")),
    ("1,250.75", Decimal("1250.75")),
    ("850.5", Decimal("850.5")),
    ("12 bao", Decimal("12")),
    (850.5, Decimal("850.5")),
    (120, Decimal("120")),
    ("", None),
    (None, None),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "--", True])
def test_parse_number_invalid(raw):
    with pytest.raises(ValueError):
        parse_number(raw)


@pytest.mark.parametrize("raw, expected", [
    (datetime(2026, 10, 1, 8, 30), date(2026, 10, 1)),
    (date(2026, 10, 3), date(2026, 10, 3)),
    ("05/10/2026", date(2026, 10, 5)),  # ngày/tháng, không phải tháng/ngày
    ("14-10-2026", date(2026, 10, 14)),
    ("2026-10-07", date(2026, 10, 7)),
    ("2/10/26", date(2026, 10, 2)),
    (46315, date(2026, 10, 20)),       # số serial của Excel
    ("46315", date(2026, 10, 20)),
    (None, None),
])
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["32/10/2026", "hôm qua", 5, "01/01/1990"])
def test_parse_date_invalid(raw):
    with pytest.raises(ValueError):
        parse_date(raw)


def test_normalize_text_strips_accents_and_units():
    assert normalize_text("Đơn giá (VNĐ)") == "don gia"
    assert normalize_text("  Mã   VT ") == "ma vt"
