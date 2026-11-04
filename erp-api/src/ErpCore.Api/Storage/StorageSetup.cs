using Microsoft.EntityFrameworkCore;

namespace ErpCore.Api.Storage;

public static class StorageSetup
{
    /// <summary>Storage:Provider = "SqlServer" (mặc định) hoặc "InMemory" để chạy thử không cần DB.</summary>
    public static IServiceCollection AddErpStorage(this IServiceCollection services, IConfiguration config)
    {
        if (IsInMemory(config))
        {
            services.AddSingleton<ITransactionStore, InMemoryTransactionStore>();
            return services;
        }

        var connectionString = config.GetConnectionString("ErpDb")
            ?? throw new InvalidOperationException("Thiếu ConnectionStrings:ErpDb");
        services.AddDbContext<ErpDbContext>(o =>
            o.UseSqlServer(connectionString, sql => sql.EnableRetryOnFailure(maxRetryCount: 5)));
        services.AddScoped<ITransactionStore, SqlServerTransactionStore>();
        return services;
    }

    /// <summary>Tạo bảng khi khởi động. Container SQL Server cần vài giây mới nhận kết nối nên thử lại vài lần.</summary>
    public static async Task InitializeStorageAsync(this IServiceProvider services, ILogger logger)
    {
        var config = services.GetRequiredService<IConfiguration>();
        if (IsInMemory(config))
        {
            logger.LogWarning("Đang dùng InMemory storage: dữ liệu sẽ mất khi tắt ứng dụng");
            return;
        }

        for (var attempt = 1; ; attempt++)
        {
            try
            {
                using var scope = services.CreateScope();
                var db = scope.ServiceProvider.GetRequiredService<ErpDbContext>();
                await db.Database.EnsureCreatedAsync();
                logger.LogInformation("Đã kết nối SQL Server");
                return;
            }
            catch (Exception ex) when (attempt < 10)
            {
                logger.LogWarning("Chưa kết nối được SQL Server (lần {Attempt}): {Message}", attempt, ex.Message);
                await Task.Delay(TimeSpan.FromSeconds(5));
            }
        }
    }

    private static bool IsInMemory(IConfiguration config) =>
        string.Equals(config["Storage:Provider"], "InMemory", StringComparison.OrdinalIgnoreCase);
}
