using System.Security.Cryptography;
using System.Text;

namespace ErpCore.Api.Security;

/// <summary>Yêu cầu header X-Api-Key khớp cấu hình Security:ApiKey cho các endpoint nội bộ.</summary>
public class ApiKeyFilter(IConfiguration config) : IEndpointFilter
{
    public const string HeaderName = "X-Api-Key";

    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var expected = config["Security:ApiKey"];
        if (string.IsNullOrEmpty(expected))
            return Results.Problem("Chưa cấu hình Security:ApiKey", statusCode: StatusCodes.Status500InternalServerError);

        var provided = context.HttpContext.Request.Headers[HeaderName].ToString();
        // So sánh thời gian cố định để không lộ key qua độ trễ phản hồi
        var ok = CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(provided), Encoding.UTF8.GetBytes(expected));
        return ok ? await next(context) : Results.Unauthorized();
    }
}
