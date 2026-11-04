import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.pipeline import process_files

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_data" / "input"


@pytest.fixture(scope="module")
def result():
    subprocess.run([sys.executable, str(ROOT / "sample_data" / "generate_samples.py")], check=True)
    return process_files(sorted(SAMPLES.glob("*.xlsx")))


def test_stats(result):
    s = result.stats
    assert s["files"] == 3 and s["sheets"] == 4
    assert s["clean_rows"] == 12
    assert s["rejected_rows"] == 3
    assert s["duplicate_rows"] == 1
    assert s["total_rows"] == 2 and s["blank_rows"] == 2


def test_vertically_merged_date_is_filled_down(result):
    ct02 = result.clean[result.clean.site_code == "CT02"]
    assert (ct02.head(3)["date"].astype(str) == "2026-10-07").all()


def test_site_code_from_title_or_filename(result):
    assert set(result.clean.site_code) == {"CT01", "CT02", "CT03"}


def test_material_code_normalized(result):
    assert "XM-PC40" in set(result.clean[result.clean.site_code == "CT02"].material_code)


def test_amount_recomputed_and_mismatch_flagged(result):
    row = result.clean[(result.clean.site_code == "CT01") & (result.clean.material_code == "DA-1X2")].iloc[0]
    assert row.amount == Decimal("12300000.00")
    warnings = result.issues[(result.issues.severity == "warning") & (result.issues.field == "amount")]
    assert len(warnings) == 1


def test_rejected_rows_have_traceable_location(result):
    errors = result.issues[result.issues.severity == "error"]
    assert set(zip(errors.file, errors.row)) == {
        ("CT02_Q7_thang10.xlsx", 8),
        ("CT03_BinhDuong_T10.xlsx", 4),
        ("CT03_BinhDuong_T10.xlsx", 5),
    }


def test_row_hash_unique_after_dedupe(result):
    assert result.clean.row_hash.is_unique
