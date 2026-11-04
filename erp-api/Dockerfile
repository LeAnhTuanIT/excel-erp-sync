FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY src/ErpCore.Api/ErpCore.Api.csproj src/ErpCore.Api/
RUN dotnet restore src/ErpCore.Api/ErpCore.Api.csproj
COPY src/ src/
RUN dotnet publish src/ErpCore.Api/ErpCore.Api.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "ErpCore.Api.dll"]
