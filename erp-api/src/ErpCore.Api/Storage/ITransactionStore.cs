using ErpCore.Api.Contracts;
using ErpCore.Api.Domain;

namespace ErpCore.Api.Storage;

/// <summary>
/// Lớp lưu trữ. Bản chạy thật dùng SQL Server qua EF Core (SqlServerTransactionStore);
/// bản InMemory dùng để demo nhanh khi chưa có SQL Server.
/// </summary>
public interface ITransactionStore
{
    /// <summary>Trả về các RowHash trong danh sách đã tồn tại trong DB.</summary>
    Task<HashSet<string>> GetExistingHashesAsync(IReadOnlyCollection<string> hashes, CancellationToken ct);

    /// <summary>Ghi các giao dịch mới trong một transaction, trả về số dòng đã ghi.</summary>
    Task<int> InsertAsync(IReadOnlyList<MaterialTransaction> items, CancellationToken ct);

    Task<PagedResult<MaterialTransaction>> QueryAsync(
        string? siteCode, DateOnly? from, DateOnly? to, int page, int pageSize, CancellationToken ct);

    Task<IReadOnlyList<SiteSummaryRow>> GetSiteSummaryAsync(DateOnly? from, DateOnly? to, CancellationToken ct);
}
