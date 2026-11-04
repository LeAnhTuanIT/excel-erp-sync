using ErpCore.Api.Contracts;
using ErpCore.Api.Domain;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

namespace ErpCore.Api.Storage;

public class SqlServerTransactionStore(ErpDbContext db) : ITransactionStore
{
    public async Task<HashSet<string>> GetExistingHashesAsync(IReadOnlyCollection<string> hashes, CancellationToken ct)
    {
        var list = hashes.ToList();
        var found = await db.MaterialTransactions.AsNoTracking()
            .Where(x => list.Contains(x.RowHash))
            .Select(x => x.RowHash)
            .ToListAsync(ct);
        return found.ToHashSet();
    }

    public async Task<int> InsertAsync(IReadOnlyList<MaterialTransaction> items, CancellationToken ct)
    {
        if (items.Count == 0) return 0;
        // Một lần SaveChanges chạy trong một transaction: hoặc ghi đủ cả batch, hoặc không ghi gì
        try
        {
            db.MaterialTransactions.AddRange(items);
            return await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex) when (IsUniqueViolation(ex))
        {
            // Một request khác vừa ghi cùng RowHash: bỏ các dòng đã tồn tại rồi ghi lại phần còn lại
            db.ChangeTracker.Clear();
            var existing = await GetExistingHashesAsync(items.Select(i => i.RowHash).ToList(), ct);
            var remaining = items.Where(i => !existing.Contains(i.RowHash)).ToList();
            remaining.ForEach(i => i.Id = 0);
            db.MaterialTransactions.AddRange(remaining);
            return await db.SaveChangesAsync(ct);
        }
    }

    // 2601/2627: lỗi vi phạm unique index / unique constraint của SQL Server
    private static bool IsUniqueViolation(DbUpdateException ex) =>
        ex.InnerException is SqlException { Number: 2601 or 2627 };

    public async Task<PagedResult<MaterialTransaction>> QueryAsync(
        string? siteCode, DateOnly? from, DateOnly? to, int page, int pageSize, CancellationToken ct)
    {
        var query = Filter(db.MaterialTransactions.AsNoTracking(), siteCode, from, to);
        var total = await query.CountAsync(ct);
        var items = await query.OrderBy(x => x.TransactionDate).ThenBy(x => x.Id)
            .Skip((page - 1) * pageSize).Take(pageSize)
            .ToListAsync(ct);
        return new PagedResult<MaterialTransaction>(page, pageSize, total, items);
    }

    public async Task<IReadOnlyList<SiteSummaryRow>> GetSiteSummaryAsync(DateOnly? from, DateOnly? to, CancellationToken ct)
    {
        // GROUP BY chạy trên SQL Server, chỉ trả về các dòng tổng hợp
        return await Filter(db.MaterialTransactions.AsNoTracking(), null, from, to)
            .GroupBy(x => new { x.SiteCode, x.MaterialCode })
            .OrderBy(g => g.Key.SiteCode).ThenBy(g => g.Key.MaterialCode)
            .Select(g => new SiteSummaryRow(
                g.Key.SiteCode, g.Key.MaterialCode,
                g.Max(x => x.MaterialName), g.Max(x => x.Unit),
                g.Sum(x => x.Quantity), g.Sum(x => x.Amount), g.Count()))
            .ToListAsync(ct);
    }

    private static IQueryable<MaterialTransaction> Filter(
        IQueryable<MaterialTransaction> source, string? siteCode, DateOnly? from, DateOnly? to)
    {
        if (siteCode != null) source = source.Where(x => x.SiteCode == siteCode);
        if (from != null) source = source.Where(x => x.TransactionDate >= from);
        if (to != null) source = source.Where(x => x.TransactionDate <= to);
        return source;
    }
}
