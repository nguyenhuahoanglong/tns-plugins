# C# Unit Tests (xUnit)

C#-specific syntax for xUnit + NSubstitute + FluentAssertions (+ FakeXrmEasy for Dataverse).
Cross-cutting principles (AAA, mock-at-boundary, `Should_<behavior>_When_<condition>` naming,
determinism, requirement->test mapping) live in `best-practices.md` — applied here, not re-explained.

## Test project setup

Name the project `<Project>.Tests`, alongside the SUT project, and reference it.

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><Nullable>enable</Nullable>
    <IsPackable>false</IsPackable></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />
    <PackageReference Include="xunit" Version="2.*" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.*" />
    <PackageReference Include="NSubstitute" Version="5.*" />
    <PackageReference Include="FluentAssertions" Version="[7.*]" /> <!-- pin v7: v8 is commercial -->
    <PackageReference Include="coverlet.collector" Version="6.*" />
  </ItemGroup>
</Project>
```

```bash
dotnet test --filter "FullyQualifiedName~OrderService"   # subset
dotnet test --collect:"XPlat Code Coverage"              # -> TestResults/**/coverage.cobertura.xml
```

> FluentAssertions v8+ needs a paid license (~$130/seat/yr). Pin `[7.*]` (Apache), use the drop-in
> fork `AwesomeAssertions`, or free `Shouldly` (`result.ShouldBe(...)`). Examples use v7 syntax.

## Plain class / service

```csharp
public class OrderServiceTests
{
    [Fact]
    public void Should_ApplyDiscount_When_CustomerIsPremium()
    {
        var repo = Substitute.For<IPriceRepository>();        // Arrange — mock at boundary
        repo.GetBasePrice("SKU1").Returns(100m);
        var total = new OrderService(repo).Quote("SKU1", isPremium: true);  // Act
        total.Should().Be(90m);                               // Assert
        repo.Received(1).GetBasePrice("SKU1");
    }

    [Theory] [InlineData(false, 100)] [InlineData(true, 90)]
    public void Should_ComputeTotal_When_GivenInputs(bool premium, decimal expected)
    {
        var repo = Substitute.For<IPriceRepository>();
        repo.GetBasePrice(Arg.Any<string>()).Returns(100m);
        new OrderService(repo).Quote("SKU1", premium).Should().Be(expected);
    }
}
```

NSubstitute: `sub.M(args).Returns(x)` · `Arg.Any<T>()` · `sub.Received(1).M(x)` · `DidNotReceive()` ·
throw via `sub.When(s => s.M()).Do(_ => throw …)` · async `.Returns(Task.FromResult(x))`.
Assertions: `.BeEquivalentTo(expected)` (deep) · `.Throw<T>().WithMessage("*partial*")` · `NotThrow()`.

## Azure Functions (.NET 8 isolated worker)

DI-first: inject deps (`ILogger<T>`, services) via the function-class constructor, then instantiate
it directly — no `FunctionContext`/trigger mocking. Test handler logic, not the binding pipeline.

```csharp
public class CheckoutFunction(ILogger<CheckoutFunction> logger, IOrderService orders)
{
    [Function("Checkout")]
    public Task<OrderResult> Run([QueueTrigger("orders")] string sku) => orders.PlaceAsync(sku);
}

[Fact]
public async Task Should_PlaceOrder_When_MessageReceived()
{
    var orders = Substitute.For<IOrderService>();
    orders.PlaceAsync("SKU1").Returns(new OrderResult("OK"));
    var sut = new CheckoutFunction(NullLogger<CheckoutFunction>.Instance, orders);  // no log mock
    (await sut.Run("SKU1")).Status.Should().Be("OK");
    await orders.Received(1).PlaceAsync("SKU1");
}
```

Use `NullLogger<T>.Instance` (Microsoft.Extensions.Logging.Abstractions) unless asserting on logs.

## Dataverse plugins (FakeXrmEasy v3)

v3 differs from v1/v2: build `IXrmFakedContext` via `MiddlewareBuilder` and **set a license**
(`NonCommercial` vs `Commercial`). Packages: `FakeXrmEasy.v9`, `.Plugins`, `.Abstractions`.

```csharp
using FakeXrmEasy.Abstractions; using FakeXrmEasy.Middleware;
using FakeXrmEasy.Middleware.Crud; using FakeXrmEasy.Plugins;

var ctx = MiddlewareBuilder.New().AddCrud().UseCrud()
    .SetLicense(FakeXrmEasyLicense.NonCommercial).Build();   // accept license terms

[Fact]
public void Should_SetFullName_When_AccountCreated()
{
    var target = new Entity("account") { Id = Guid.NewGuid(), ["firstname"] = "Ada" };
    var pc = ctx.GetDefaultPluginContext();
    pc.MessageName = "Create"; pc.Stage = 20;                 // PreOperation
    pc.InputParameters = new ParameterCollection { { "Target", target } };

    ctx.ExecutePluginWith<SetNameOnCreate>(pc);               // wires IServiceProvider + Execute

    target.GetAttributeValue<string>("fullname").Should().Be("Ada");
}
```

Pipeline simulation (auto-fires registered steps on CRUD): `.AddPipelineSimulation().UsePipelineSimulation()`,
then `ctx.RegisterPluginStep<MyPlugin>(...)` and call `service.Create(entity)`.

**Simpler alternative — mock `IOrganizationService` with NSubstitute** (no in-memory DB; use when the
plugin only calls service methods): stub `IServiceProvider.GetService(...)` to return a substituted
`IPluginExecutionContext`, `IOrganizationServiceFactory` (→ your `IOrganizationService`), and
`ITracingService`; call `plugin.Execute(sp)`; assert `service.Received(1).Update(Arg.Is<Entity>(...))`.

## Determinism

Never call `DateTime.Now`/`UtcNow` or `Guid.NewGuid()` in the SUT — inject them.

```csharp
public class Invoicer(TimeProvider clock, Func<Guid> newId) { /* clock.GetUtcNow(); newId(); */ }

var clock = new FakeTimeProvider(new DateTimeOffset(2026,1,1,0,0,0,TimeSpan.Zero)); // *.TimeProvider.Testing
var sut = new Invoicer(clock, () => Guid.Parse("00000000-0000-0000-0000-000000000001"));
```

Repositories: EF Core in-memory provider, unique DB name per test for isolation —
`new DbContextOptionsBuilder<AppDb>().UseInMemoryDatabase(Guid.NewGuid().ToString()).Options`.

## Legacy C# (characterization)

No tests on legacy code: pin current behavior before changing it (see `legacy-characterization.md`).

- **Snapshot/approval** with `Verify` (`VerifyXunit`): `[Fact] public Task M() => Verify(sut.Render(input));`
  First run writes `*.received.txt`; review and rename to `*.verified.txt` to lock the baseline.
  (`ApprovalTests` is an older equivalent.)
- **Find a seam**: extract an interface over the static/`new`/IO call and constructor-inject it so the
  test can substitute a fake. Make the smallest seam change; the characterization test guards the refactor.
