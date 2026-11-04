# Excel → ERP Sync

Gộp báo cáo xuất vật tư từ nhiều công trình (mỗi nơi một mẫu Excel khác nhau), làm sạch dữ liệu bẩn, đồng bộ vào một "ERP core" viết bằng C# trên SQL Server, và xuất báo cáo Excel tổng hợp có pivot, biểu đồ, định dạng có điều kiện.

```
 Nhiều file .xlsx "bẩn"         ETL (Python)                      ERP core (C#)                 SQL Server
 ┌─────────────────────┐   ┌───────────────────────────┐   ┌────────────────────────────┐   ┌──────────────────┐
 │ CT01: header dòng 5 │   │ OpenPyXL: gỡ merged cell,  │   │ ASP.NET Core Minimal API   │   │ MaterialTransac- │
 │ CT02: tiền "95.000đ"├──►│ tìm header, map tên cột    ├──►│ - kiểm tra lại dữ liệu     ├──►│ tions            │
 │ CT03: 2 sheet/tuần  │   │ Pandas: parse ngày/tiền,   │   │ - idempotent theo RowHash  │   │ unique(RowHash)  │
 └─────────────────────┘   │ lọc trùng, đối soát tiền   │   │ - báo cáo GROUP BY         │   └──────────────────┘
                           │ XlsxWriter: báo cáo Excel  │   │ EF Core 8                  │
                           └───────────────────────────┘   └────────────────────────────┘
```

| Thành phần | Công nghệ |
|---|---|
| `etl/` | Python 3.12, Pandas, OpenPyXL, XlsxWriter, FastAPI, httpx, pytest |
| `erp-api/` | C# / .NET 8, ASP.NET Core Minimal API, EF Core 8, SQL Server 2022 |
| `erp-api/sql/` | T-SQL: view, stored procedure, window function |
| `sample_data/` | Script sinh 3 file Excel mẫu cố tình chứa lỗi |

## Dữ liệu bẩn được xử lý

| Vấn đề trong file | Cách xử lý | Code |
|---|---|---|
| Tiêu đề merge ở đầu file, header không nằm ở dòng 1 | Quét 20 dòng đầu, chọn dòng khớp nhiều tên cột nhất | `reader.find_header` |
| Tên cột mỗi nơi một kiểu ("Mã VT", "Mã vật tư", "Ma VT", "Đơn giá (VNĐ)") | Bỏ dấu, bỏ phần trong ngoặc, so với bảng alias | `reader.COLUMN_ALIASES` |
| Ô "Ngày" merge dọc cho nhiều dòng | Gỡ merge và chép giá trị xuống mọi ô trong vùng | `reader.unmerge_and_fill` |
| Ngày dạng `datetime`, chuỗi `05/10/2026`, `2/10/26`, số serial `46315` | Ưu tiên ngày/tháng/năm; số serial tính từ mốc 30/12/1899 | `parsers.parse_date` |
| Tiền `"1.250.000 đ"`, số lượng `"1,5"`, `"1.250,5"` | Dấu `.` là hàng nghìn, `,` là thập phân (kiểu VN); dùng `Decimal` | `parsers.parse_number` |
| Dòng trống, dòng "Tổng cộng" | Bỏ qua và đếm vào thống kê | `pipeline._is_total_row` |
| Thiếu mã công trình trong file | Lấy từ tiêu đề, không có thì lấy từ tên file | `reader.detect_site_code` |
| Thành tiền nhập tay sai hoặc bỏ trống | Tính lại SL × đơn giá, ghi cảnh báo kèm số lệch để đối soát | `pipeline._process_table` |
| Cùng một dòng gửi 2 lần | Băm SHA-256 (công trình, ngày, mã VT, SL, đơn giá), giữ bản đầu tiên | `pipeline._drop_duplicates` |
| Dòng sai (ngày 32/10, SL "abc", thiếu mã VT) | Loại dòng, ghi lại file / sheet / số dòng Excel / giá trị gốc | sheet "Van de" |

## Chạy bằng Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

- ERP API: http://localhost:5080 (SQL Server cần khoảng 20–30 giây để sẵn sàng, API tự thử kết nối lại)
- ETL API (Swagger): http://localhost:8000/docs

Đẩy 3 file mẫu vào ERP rồi xem báo cáo:

```bash
curl -F "files=@sample_data/input/CT01_ThuDuc_T10.xlsx" \
     -F "files=@sample_data/input/CT02_Q7_thang10.xlsx" \
     -F "files=@sample_data/input/CT03_BinhDuong_T10.xlsx" \
     "http://localhost:8000/ingest?push=true"

curl -H "X-Api-Key: dev-api-key-change-me" \
     "http://localhost:5080/api/reports/site-summary?from=2026-10-01&to=2026-10-31"
```

Chạy lại lệnh `ingest` lần hai: ERP trả `inserted: 0, skipped: 12`, không ghi trùng.

Chạy các báo cáo T-SQL:

```bash
docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Your_strong_Passw0rd" -C -d ErpCore -i /sql/reports.sql
docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Your_strong_Passw0rd" -C -d ErpCore \
  -Q "EXEC dbo.usp_SiteMaterialSummary @From='2026-10-01', @To='2026-10-31'"
```

> Image SQL Server chỉ có bản x86-64. Trên Mac chip Apple cần bật Rosetta trong Docker Desktop.

## Chạy không cần Docker

```bash
# ERP API, lưu trong RAM (không cần SQL Server)
cd erp-api/src/ErpCore.Api
dotnet run --launch-profile inmemory

# ETL
cd etl
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python ../sample_data/generate_samples.py
python -m pytest -q
python -m app.cli ../sample_data/input/*.xlsx --report out/bao_cao_vat_tu.xlsx --push
```

## ERP API

Tất cả endpoint dưới `/api` yêu cầu header `X-Api-Key`.

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra sống |
| POST | `/api/material-transactions/batch` | Ghi tối đa 1000 dòng; dòng đã có (theo `row_hash`) bị bỏ qua |
| GET | `/api/material-transactions?siteCode=&from=&to=&page=&pageSize=` | Tra cứu có phân trang |
| GET | `/api/reports/site-summary?from=&to=` | Tổng số lượng, thành tiền theo công trình × vật tư |

Batch sai trả `400` kèm danh sách lỗi theo dòng và không ghi dòng nào (all-or-nothing).

## Báo cáo Excel xuất ra

| Sheet | Nội dung |
|---|---|
| Tong quan | Thống kê lần chạy, tổng chi phí theo công trình (cột Tổng là công thức `SUM` thật), biểu đồ cột |
| Pivot | Chi phí theo vật tư × công trình, có dòng/cột Tổng, thang màu |
| Du lieu sach | Excel Table có filter, định dạng ngày/tiền, data bar, cột truy vết file/sheet/dòng gốc |
| Van de | Lỗi / cảnh báo / thông tin, tô màu theo mức độ, có filter |

## Quyết định thiết kế

- **ERP vẫn kiểm tra lại dữ liệu** dù ETL đã làm sạch, vì API có thể bị gọi từ nguồn khác.
- **Idempotent bằng `RowHash` + unique index**: gửi lại file không sinh dữ liệu trùng. Unique index là chốt chặn cuối khi 2 request chạy song song; trường hợp đó được bắt riêng (lỗi SQL 2601/2627).
- **Tiền dùng `Decimal` / `decimal(18,2)`, gửi qua JSON dạng chuỗi** để không bị sai số dấu phẩy động.
- **Tính lại thành tiền** thay vì tin số nhập tay, nhưng vẫn ghi số lệch để kế toán đối soát.
- **Giữ vị trí gốc (file, sheet, dòng)** cho mọi dòng sạch và mọi lỗi để người gửi sửa đúng chỗ.
- **Tách lớp lưu trữ (`ITransactionStore`)**: SQL Server khi chạy thật, InMemory khi demo.

## Giới hạn hiện tại

- Sheet "Pivot" là bảng tổng hợp do Pandas tính sẵn, không phải đối tượng PivotTable của Excel (XlsxWriter không tạo được PivotTable).
- Hai dòng hoàn toàn giống nhau (cùng công trình, ngày, vật tư, SL, đơn giá) được coi là trùng. Nếu nghiệp vụ cho phép 2 phiếu như vậy thì cần thêm số phiếu vào khóa.
- Khi số phân cách mơ hồ, ví dụ `1.250`, hệ thống hiểu theo kiểu Việt Nam là 1250.
- Bảng được tạo bằng `EnsureCreated`; dự án thật nên dùng EF Core Migrations.
- Xác thực chỉ dùng API key, phù hợp cho gọi nội bộ giữa các service.
