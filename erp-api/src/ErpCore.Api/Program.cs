using System.Text.Json;
using System.Text.Json.Serialization;
using ErpCore.Api.Contracts;
using ErpCore.Api.Security;
using ErpCore.Api.Services;
using ErpCore.Api.Storage;

var builder = WebApplication.CreateBuilder(args);

// ETL Python gửi JSON dạng snake_case và gửi số tiền dạng chuỗi để không mất độ chính xác
builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    o.SerializerOptions.NumberHandling = JsonNumberHandling.AllowReadingFromString;
});

builder.Services.AddErpStorage(builder.Configuration);
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddScoped<ImportService>();

var app = builder.Build();
await app.Services.InitializeStorageAsync(app.Logger);

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

var api = app.MapGroup("/api").AddEndpointFilter<ApiKeyFilter>();

api.MapPost("/material-transactions/batch", async (ImportBatchRequest request, ImportService service, CancellationToken ct) =>
{
    var (result, errors) = await service.ImportAsync(request.Items ?? [], ct);
    return result is null
        ? Results.BadRequest(new { message = "Dữ liệu không hợp lệ, không dòng nào được ghi", errors })
        : Results.Ok(result);
});

api.MapGet("/material-transactions", async (
    ITransactionStore store, string? siteCode, DateOnly? from, DateOnly? to,
    int page = 1, int pageSize = 50, CancellationToken ct = default) =>
{
    page = Math.Max(page, 1);
    pageSize = Math.Clamp(pageSize, 1, 500);
    return Results.Ok(await store.QueryAsync(siteCode?.ToUpperInvariant(), from, to, page, pageSize, ct));
});

api.MapGet("/reports/site-summary", async (ITransactionStore store, DateOnly? from, DateOnly? to, CancellationToken ct) =>
    Results.Ok(await store.GetSiteSummaryAsync(from, to, ct)));

app.Run();
