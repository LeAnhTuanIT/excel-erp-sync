namespace ErpCore.Api.Contracts;

public record MaterialTransactionDto(
    string SiteCode,
    DateOnly Date,
    string MaterialCode,
    string? MaterialName,
    string? Unit,
    decimal Quantity,
    decimal UnitPrice,
    decimal Amount,
    string RowHash,
    string? SourceFile,
    string? SourceSheet,
    int? SourceRow);

public record ImportBatchRequest(List<MaterialTransactionDto> Items);

public record ImportBatchResult(int Received, int Inserted, int Skipped);

public record RowError(int Index, string Field, string Message);

public record SiteSummaryRow(
    string SiteCode,
    string MaterialCode,
    string? MaterialName,
    string? Unit,
    decimal TotalQuantity,
    decimal TotalAmount,
    int TransactionCount);

public record PagedResult<T>(int Page, int PageSize, int Total, IReadOnlyList<T> Items);
