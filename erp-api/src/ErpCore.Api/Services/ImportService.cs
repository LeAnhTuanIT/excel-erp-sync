using ErpCore.Api.Contracts;
using ErpCore.Api.Domain;
using ErpCore.Api.Storage;

namespace ErpCore.Api.Services;

public class ImportService(ITransactionStore store, TimeProvider clock)
{
    public const int MaxBatchSize = 1000;
    private const decimal AmountTolerance = 1m;

    /// <summary>
    /// Kiểm tra lại dữ liệu phía ERP (không tin hoàn toàn vào ETL), rồi ghi các dòng chưa có.
    /// Gửi lại cùng một batch nhiều lần cho kết quả như nhau: lần sau Inserted = 0.
    /// </summary>
    public async Task<(ImportBatchResult? Result, List<RowError> Errors)> ImportAsync(
        IReadOnlyList<MaterialTransactionDto> items, CancellationToken ct)
    {
        var errors = Validate(items);
        if (errors.Count > 0) return (null, errors);

        // Lọc trùng trong chính batch, sau đó lọc các dòng đã có trong DB
        var unique = items.GroupBy(i => i.RowHash).Select(g => g.First()).ToList();
        var existing = await store.GetExistingHashesAsync(unique.Select(i => i.RowHash).ToList(), ct);
        var now = clock.GetUtcNow().UtcDateTime;
        var toInsert = unique.Where(i => !existing.Contains(i.RowHash)).Select(i => ToEntity(i, now)).ToList();

        var inserted = await store.InsertAsync(toInsert, ct);
        return (new ImportBatchResult(items.Count, inserted, items.Count - inserted), errors);
    }

    public static List<RowError> Validate(IReadOnlyList<MaterialTransactionDto> items)
    {
        var errors = new List<RowError>();
        if (items.Count == 0) errors.Add(new RowError(-1, "items", "Batch rỗng"));
        if (items.Count > MaxBatchSize) errors.Add(new RowError(-1, "items", $"Tối đa {MaxBatchSize} dòng mỗi batch"));

        for (var i = 0; i < items.Count; i++)
        {
            var x = items[i];
            if (string.IsNullOrWhiteSpace(x.SiteCode)) errors.Add(new RowError(i, "site_code", "Bắt buộc"));
            if (string.IsNullOrWhiteSpace(x.MaterialCode)) errors.Add(new RowError(i, "material_code", "Bắt buộc"));
            if (x.Date == default) errors.Add(new RowError(i, "date", "Bắt buộc"));
            if (x.Quantity <= 0) errors.Add(new RowError(i, "quantity", "Phải lớn hơn 0"));
            if (x.UnitPrice < 0) errors.Add(new RowError(i, "unit_price", "Không được âm"));
            if (Math.Abs(x.Quantity * x.UnitPrice - x.Amount) > AmountTolerance)
                errors.Add(new RowError(i, "amount", "Thành tiền không khớp Số lượng x Đơn giá"));
            if (x.RowHash is not { Length: 64 }) errors.Add(new RowError(i, "row_hash", "Phải là SHA-256 dạng hex (64 ký tự)"));
        }
        return errors;
    }

    private static MaterialTransaction ToEntity(MaterialTransactionDto x, DateTime now) => new()
    {
        SiteCode = x.SiteCode.Trim().ToUpperInvariant(),
        TransactionDate = x.Date,
        MaterialCode = x.MaterialCode.Trim().ToUpperInvariant(),
        MaterialName = x.MaterialName,
        Unit = x.Unit,
        Quantity = x.Quantity,
        UnitPrice = x.UnitPrice,
        Amount = x.Amount,
        RowHash = x.RowHash.ToLowerInvariant(),
        SourceFile = x.SourceFile,
        SourceSheet = x.SourceSheet,
        SourceRow = x.SourceRow,
        ImportedAtUtc = now,
    };
}
