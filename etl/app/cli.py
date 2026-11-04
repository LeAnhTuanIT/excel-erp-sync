"""Chạy ETL từ dòng lệnh.

    python -m app.cli ../sample_data/input/*.xlsx --report out/bao_cao.xlsx
    python -m app.cli ../sample_data/input/*.xlsx --report out/bao_cao.xlsx --push
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .erp_client import ErpClient
from .pipeline import process_files
from .report import export_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gộp và làm sạch báo cáo vật tư từ nhiều file Excel")
    parser.add_argument("files", nargs="+", type=Path, help="Các file .xlsx đầu vào")
    parser.add_argument("--report", type=Path, default=Path("out/bao_cao_vat_tu.xlsx"), help="File báo cáo xuất ra")
    parser.add_argument("--push", action="store_true", help="Đẩy dữ liệu sạch sang ERP API")
    args = parser.parse_args(argv)

    missing = [str(f) for f in args.files if not f.exists()]
    if missing:
        print(f"Không tìm thấy file: {', '.join(missing)}", file=sys.stderr)
        return 2

    result = process_files(args.files)
    s = result.stats
    print(f"Đọc {s['files']} file / {s['sheets']} sheet: {s['clean_rows']} dòng hợp lệ, "
          f"{s['rejected_rows']} dòng lỗi, {s['duplicate_rows']} dòng trùng")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    export_report(result, args.report)
    print(f"Đã xuất báo cáo: {args.report}")

    if args.push:
        pushed = ErpClient().push(result.clean)
        print(f"ERP: nhận {pushed.received}, ghi mới {pushed.inserted}, bỏ qua (đã có) {pushed.skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
