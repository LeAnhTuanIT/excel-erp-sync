/*
  Báo cáo T-SQL chạy trực tiếp trên database ErpCore (bảng do EF Core tạo khi API khởi động).
  Chạy bằng Azure Data Studio / SSMS, hoặc:
    docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d ErpCore -i /sql/reports.sql
*/
SET NOCOUNT ON;
GO

-- Chi phí vật tư theo công trình theo tháng
CREATE OR ALTER VIEW dbo.vw_MonthlySiteCost
AS
SELECT
    SiteCode,
    DATEFROMPARTS(YEAR(TransactionDate), MONTH(TransactionDate), 1) AS MonthStart,
    COUNT_BIG(*)  AS TransactionCount,
    SUM(Amount)   AS TotalAmount
FROM dbo.MaterialTransactions
GROUP BY SiteCode, DATEFROMPARTS(YEAR(TransactionDate), MONTH(TransactionDate), 1);
GO

-- Tổng hợp theo công trình x vật tư trong khoảng ngày, kèm tỷ trọng chi phí trong công trình
CREATE OR ALTER PROCEDURE dbo.usp_SiteMaterialSummary
    @From DATE,
    @To   DATE
AS
BEGIN
    SET NOCOUNT ON;

    WITH agg AS (
        SELECT
            SiteCode,
            MaterialCode,
            MAX(MaterialName) AS MaterialName,
            MAX(Unit)         AS Unit,
            SUM(Quantity)     AS TotalQuantity,
            SUM(Amount)       AS TotalAmount
        FROM dbo.MaterialTransactions
        WHERE TransactionDate >= @From AND TransactionDate <= @To   -- điều kiện sargable, dùng được index
        GROUP BY SiteCode, MaterialCode
    )
    SELECT
        SiteCode,
        MaterialCode,
        MaterialName,
        Unit,
        TotalQuantity,
        TotalAmount,
        CAST(100.0 * TotalAmount / NULLIF(SUM(TotalAmount) OVER (PARTITION BY SiteCode), 0) AS DECIMAL(5, 2)) AS PctOfSite,
        RANK() OVER (PARTITION BY SiteCode ORDER BY TotalAmount DESC) AS CostRank
    FROM agg
    ORDER BY SiteCode, CostRank;
END;
GO

-- Đơn giá bất thường: cùng vật tư nhưng đơn giá lệch hơn 10% so với trung bình toàn hệ thống
CREATE OR ALTER VIEW dbo.vw_UnitPriceOutliers
AS
WITH stats AS (
    SELECT MaterialCode, AVG(UnitPrice) AS AvgPrice
    FROM dbo.MaterialTransactions
    GROUP BY MaterialCode
)
SELECT
    t.SiteCode, t.TransactionDate, t.MaterialCode, t.UnitPrice, s.AvgPrice,
    CAST(100.0 * (t.UnitPrice - s.AvgPrice) / NULLIF(s.AvgPrice, 0) AS DECIMAL(7, 2)) AS PctDiff,
    t.SourceFile, t.SourceSheet, t.SourceRow
FROM dbo.MaterialTransactions t
JOIN stats s ON s.MaterialCode = t.MaterialCode
WHERE ABS(t.UnitPrice - s.AvgPrice) > 0.1 * s.AvgPrice;
GO

-- Ví dụ:
-- EXEC dbo.usp_SiteMaterialSummary @From = '2026-10-01', @To = '2026-10-31';
-- SELECT * FROM dbo.vw_MonthlySiteCost ORDER BY SiteCode, MonthStart;
-- SELECT * FROM dbo.vw_UnitPriceOutliers ORDER BY ABS(PctDiff) DESC;
