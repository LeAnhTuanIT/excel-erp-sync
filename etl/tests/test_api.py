from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api import app

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data" / "input"
client = TestClient(app)


def _upload():
    return [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in sorted(SAMPLES.glob("*.xlsx"))]


def test_ingest_returns_stats_and_issues():
    resp = client.post("/ingest", files=_upload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["stats"]["clean_rows"] == 12
    assert any(i["severity"] == "error" and i["row"] == 8 for i in body["issues"])


def test_report_returns_formatted_workbook():
    resp = client.post("/report", files=_upload())
    assert resp.status_code == 200
    wb = load_workbook(BytesIO(resp.content))
    assert wb.sheetnames == ["Tong quan", "Pivot", "Du lieu sach", "Van de"]


def test_rejects_non_excel_upload():
    resp = client.post("/ingest", files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert resp.status_code == 400
