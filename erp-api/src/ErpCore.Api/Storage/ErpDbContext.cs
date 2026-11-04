using ErpCore.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace ErpCore.Api.Storage;

public class ErpDbContext(DbContextOptions<ErpDbContext> options) : DbContext(options)
{
    public DbSet<MaterialTransaction> MaterialTransactions => Set<MaterialTransaction>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        var e = modelBuilder.Entity<MaterialTransaction>();
        e.ToTable("MaterialTransactions");
        e.HasKey(x => x.Id);
        e.Property(x => x.SiteCode).HasMaxLength(20).IsRequired();
        e.Property(x => x.MaterialCode).HasMaxLength(50).IsRequired();
        e.Property(x => x.MaterialName).HasMaxLength(200);
        e.Property(x => x.Unit).HasMaxLength(20);
        // Tiền và số lượng dùng decimal, không dùng float, để không sai số khi cộng dồn
        e.Property(x => x.Quantity).HasPrecision(18, 3);
        e.Property(x => x.UnitPrice).HasPrecision(18, 2);
        e.Property(x => x.Amount).HasPrecision(18, 2);
        e.Property(x => x.RowHash).HasMaxLength(64).IsFixedLength().IsRequired();
        e.Property(x => x.SourceFile).HasMaxLength(260);
        e.Property(x => x.SourceSheet).HasMaxLength(100);

        // Chốt chặn cuối cùng chống ghi trùng, kể cả khi 2 request chạy song song
        e.HasIndex(x => x.RowHash).IsUnique();
        // Phục vụ lọc theo công trình + khoảng ngày và báo cáo tổng hợp
        e.HasIndex(x => new { x.SiteCode, x.TransactionDate });
    }
}
