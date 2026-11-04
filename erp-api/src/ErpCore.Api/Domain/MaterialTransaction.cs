namespace ErpCore.Api.Domain;

/// <summary>Một dòng xuất vật tư đã được làm sạch, lưu trong ERP.</summary>
public class MaterialTransaction
{
    public long Id { get; set; }
    public string SiteCode { get; set; } = "";
    public DateOnly TransactionDate { get; set; }
    public string MaterialCode { get; set; } = "";
    public string? MaterialName { get; set; }
    public string? Unit { get; set; }
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal Amount { get; set; }

    /// <summary>Khóa idempotent do ETL tính (SHA-256), có unique index để không ghi trùng.</summary>
    public string RowHash { get; set; } = "";

    // Truy vết về file gốc để kế toán đối chiếu khi cần
    public string? SourceFile { get; set; }
    public string? SourceSheet { get; set; }
    public int? SourceRow { get; set; }
    public DateTime ImportedAtUtc { get; set; }
}
