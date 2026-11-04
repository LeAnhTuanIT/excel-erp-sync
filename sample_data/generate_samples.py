"""Sinh bộ file Excel "bẩn" mô phỏng báo cáo vật tư gửi về từ các công trình.

Mỗi công trình dùng một mẫu báo cáo khác nhau, cố tình chứa các lỗi hay gặp:
- dòng tiêu đề / merged cell ở đầu file, header không nằm ở dòng 1
- tên cột khác nhau giữa các file ("Mã VT" / "Mã vật tư" / "Ma VT")
- ô ngày bị merge theo chiều dọc, ngày dạng chuỗi, ngày dạng số serial của Excel
- số tiền dạng chuỗi "1.250.000 đ", số lượng dùng dấu phẩy thập phân "1,5"
- dòng trống, dòng "Tổng cộng", dòng trùng lặp, dòng dữ liệu lỗi

Chạy:  python sample_data/generate_samples.py
"""
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

OUT = Path(__file__).parent / "input"


def site_ct01(path: Path) -> None:
    """Mẫu chuẩn nhất: có tiêu đề merge, header ở dòng 5, có dòng tổng và dòng trùng."""
    wb = Workbook()
    ws = wb.active
    ws.title = "T10-2026"
    ws.merge_cells("A1:H1")
    ws["A1"] = "BÁO CÁO XUẤT VẬT TƯ THÁNG 10/2026"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.merge_cells("A2:H2")
    ws["A2"] = "Công trình: CT01 - Chung cư Thủ Đức"
    ws.merge_cells("A3:H3")
    ws["A3"] = "Người lập: Nguyễn Văn A"
    ws.append([])
    ws.append(["STT", "Ngày", "Mã VT", "Tên vật tư", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền"])
    rows = [
        [1, datetime(2026, 10, 1), "XM-PC40", "Xi măng PC40", "bao", 120, 95000, 11400000],
        [2, datetime(2026, 10, 1), "THEP-D10", "Thép phi 10", "kg", 850.5, 18500, 15734250],
        [3, "05/10/2026", "CAT-VANG", "Cát vàng", "m3", 25, 320000, 8000000],
        [None, None, None, None, None, None, None, None],
        [4, "12/10/2026", "GACH-4L", "Gạch 4 lỗ", "viên", 12000, 1350, 16200000],
        # Dòng trùng lặp hoàn toàn với dòng 2 (gửi nhầm 2 lần)
        [5, datetime(2026, 10, 1), "THEP-D10", "Thép phi 10", "kg", 850.5, 18500, 15734250],
        # Thành tiền nhập tay bị sai so với SL x Đơn giá
        [6, "20/10/2026", "DA-1X2", "Đá 1x2", "m3", 30, 410000, 12400000],
        [None, None, None, "Tổng cộng", None, None, None, "=SUM(H6:H12)"],
    ]
    for r in rows:
        ws.append(r)
    wb.save(path)


def site_ct02(path: Path) -> None:
    """Header ở dòng 2, tên cột khác, ngày merge dọc, tiền và số lượng dạng chuỗi."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "CT02 - Nhà xưởng Quận 7 - Báo cáo tháng 10"
    ws.append(["Ngày xuất", "Mã vật tư", "Tên VT", "Đơn vị", "SL", "Đơn giá (VNĐ)", "Thành tiền (VNĐ)", "Ghi chú"])
    data = [
        ["2026-10-07", " xm-pc40 ", "Xi măng PC40", "Bao", "200", "95.000 đ", "19.000.000 đ", ""],
        [None, "thep-d10", "Thép phi 10", "Kg", "1.250,5", "18.500", "23.134.250", "giao 2 đợt"],
        [None, "SON-NUOC", "Sơn nước ngoại thất", "Thùng", "1,5", "1.250.000 đ", "", "thiếu thành tiền"],
        [46315, "CAT-VANG", "Cát vàng", "m3", "40", "320000", "12.800.000", "ngày dạng số serial"],
        ["", "", "", "", "", "", "", ""],
        ["14-10-2026", "ONG-PVC21", "Ống PVC phi 21", "Cây", "abc", "45.000", "", "số lượng lỗi"],
    ]
    for r in data:
        ws.append(r)
    # Ngày 07/10 merge dọc cho 3 dòng đầu (A3:A5)
    ws.merge_cells("A3:A5")
    wb.save(path)


def site_ct03(path: Path) -> None:
    """Hai sheet theo tuần, không có cột mã công trình (lấy từ tên file), ngày viết tắt."""
    wb = Workbook()
    w1 = wb.active
    w1.title = "Tuan 1"
    w1.append(["Ngay", "Ma VT", "Ten vat tu", "DVT", "So luong", "Don gia", "Thanh tien"])
    w1.append(["2/10/26", "XM-PC40", "Xi măng PC40", "bao", 80, 96000, 7680000])
    w1.append([date(2026, 10, 3), "GACH-4L", "Gạch 4 lỗ", "viên", 5000, 1350, 6750000])
    w1.append(["32/10/2026", "DA-1X2", "Đá 1x2", "m3", 10, 410000, 4100000])  # ngày không hợp lệ
    w2 = wb.create_sheet("Tuan 2")
    w2["A1"] = "Tuần 2"
    w2.append([])
    w2.append(["Ngay", "Ma VT", "Ten vat tu", "DVT", "So luong", "Don gia", "Thanh tien"])
    w2.append(["09/10/2026", "THEP-D10", "Thép phi 10", "kg", 300, 18500, 5550000])
    w2.append(["10/10/2026", "", "Đinh 5 phân", "kg", 12, 32000, 384000])  # thiếu mã VT
    w2.append(["TỔNG", None, None, None, None, None, 9934000])
    wb.save(path)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    site_ct01(OUT / "CT01_ThuDuc_T10.xlsx")
    site_ct02(OUT / "CT02_Q7_thang10.xlsx")
    site_ct03(OUT / "CT03_BinhDuong_T10.xlsx")
    print(f"Đã tạo file mẫu trong {OUT}")
