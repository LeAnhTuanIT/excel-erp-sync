"""FastAPI: upload file Excel, nhận về kết quả kiểm tra hoặc file báo cáo."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .erp_client import ErpClient
from .pipeline import process_files
from .report import export_report

MAX_FILES = 200
MAX_FILE_BYTES = 10 * 1024 * 1024

app = FastAPI(title="Excel → ERP ETL", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(files: list[UploadFile], push: bool = Query(False, description="Đẩy dữ liệu sạch sang ERP")) -> dict:
    """Kiểm tra và làm sạch file; trả về thống kê + danh sách vấn đề theo dòng."""
    workdir = _save_uploads(files)
    try:
        result = process_files(sorted(workdir.glob("*/*.xlsx")))
        body = {
            "stats": result.stats,
            "issues": result.issues.astype(object).where(result.issues.notna(), None).to_dict("records"),
        }
        if push and not result.clean.empty:
            pushed = ErpClient().push(result.clean)
            body["erp"] = pushed.__dict__
        return body
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@app.post("/report")
def report(files: list[UploadFile]) -> FileResponse:
    """Trả về file báo cáo Excel đã định dạng."""
    workdir = _save_uploads(files)
    result = process_files(sorted(workdir.glob("*/*.xlsx")))
    out = export_report(result, workdir / "bao_cao_vat_tu.xlsx")
    return FileResponse(
        out, filename="bao_cao_vat_tu.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(shutil.rmtree, workdir, ignore_errors=True),
    )


def _save_uploads(files: list[UploadFile]) -> Path:
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"Cần từ 1 đến {MAX_FILES} file")
    workdir = Path(tempfile.mkdtemp(prefix="etl-"))
    for i, f in enumerate(files):
        name = Path(f.filename or "").name  # bỏ đường dẫn để tránh ghi ra ngoài thư mục tạm
        if not name.lower().endswith(".xlsx"):
            shutil.rmtree(workdir, ignore_errors=True)
            raise HTTPException(400, f"Chỉ nhận file .xlsx: {name}")
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            shutil.rmtree(workdir, ignore_errors=True)
            raise HTTPException(413, f"File quá lớn (tối đa 10MB): {name}")
        # Mỗi file một thư mục con để 2 file trùng tên không ghi đè nhau
        target = workdir / f"{i:03d}" / name
        target.parent.mkdir()
        target.write_bytes(data)
    return workdir
