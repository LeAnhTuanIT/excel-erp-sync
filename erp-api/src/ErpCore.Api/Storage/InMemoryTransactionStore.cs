using ErpCore.Api.Contracts;
using ErpCore.Api.Domain;

namespace ErpCore.Api.Storage;

/// <summary>Lưu trong RAM (mất khi tắt app). Chỉ dùng cho demo hoặc chạy thử không cần SQL Server.</summary>
public class InMemoryTransactionStore : ITransactionStore
{
    private readonly List<MaterialTransaction> _items = new();
    private readonly object _lock = new();
    private long _nextId = 1;

    public Task<HashSet<string>> GetExistingHashesAsync(IReadOnlyCollection<string> hashes, CancellationToken ct)
    {
        lock (_lock)
        {
            var wanted = hashes.ToHashSet();
            return Task.FromResult(_items.Where(x => wanted.Contains(x.RowHash)).Select(x => x.RowHash).ToHashSet());
        }
    }

    public Task<int> InsertAsync(IReadOnlyList<MaterialTransaction> items, CancellationToken ct)
    {
        lock (_lock)
        {
            var existing = _items.Select(x => x.RowHash).ToHashSet();
            var inserted = 0;
            foreach (var item in items.Where(i => existing.Add(i.RowHash)))
            {
                item.Id = _nextId++;
                _items.Add(item);
                inserted++;
            }
            return Task.FromResult(inserted);
        }
    }

    public Task<PagedResult<MaterialTransaction>> QueryAsync(
        string? siteCode, DateOnly? from, DateOnly? to, int page, int pageSize, CancellationToken ct)
    {
        lock (_lock)
        {
            var query = Filter(_items, siteCode, from, to).OrderBy(x => x.TransactionDate).ThenBy(x => x.Id).ToList();
            var items = query.Skip((page - 1) * pageSize).Take(pageSize).ToList();
            return Task.FromResult(new PagedResult<MaterialTransaction>(page, pageSize, query.Count, items));
        }
    }

    public Task<IReadOnlyList<SiteSummaryRow>> GetSiteSummaryAsync(DateOnly? from, DateOnly? to, CancellationToken ct)
    {
        lock (_lock)
        {
            IReadOnlyList<SiteSummaryRow> rows = Filter(_items, null, from, to)
                .GroupBy(x => new { x.SiteCode, x.MaterialCode })
                .Select(g => new SiteSummaryRow(
                    g.Key.SiteCode, g.Key.MaterialCode,
                    g.Max(x => x.MaterialName), g.Max(x => x.Unit),
                    g.Sum(x => x.Quantity), g.Sum(x => x.Amount), g.Count()))
                .OrderBy(r => r.SiteCode).ThenBy(r => r.MaterialCode)
                .ToList();
            return Task.FromResult(rows);
        }
    }

    private static IEnumerable<MaterialTransaction> Filter(
        IEnumerable<MaterialTransaction> source, string? siteCode, DateOnly? from, DateOnly? to) =>
        source.Where(x => (siteCode == null || x.SiteCode == siteCode)
                          && (from == null || x.TransactionDate >= from)
                          && (to == null || x.TransactionDate <= to));
}
