# Economy API Reference

4 endpoints for macroeconomic data.

## Endpoints

### Treasury Yields — `client.list_treasury_yields(date_gte=..., date_lte=...)`
Daily US Treasury yield curve across maturities (1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y).
```python
for y in client.list_treasury_yields(date_gte="2024-01-01"):
    print(y.date, y.yield_1_month, y.yield_2_year, y.yield_10_year, y.yield_30_year)
```

**Use cases:**
- Compute 2Y/10Y spread (recession indicator — inverted = warning)
- Risk-free rate input for DCF/CAPM models
- Bond portfolio analysis
- Carry trade signals

### Inflation (CPI) — `client.list_inflation(date_gte=..., date_lte=...)`
Consumer Price Index, monthly.

### Inflation Expectations — `client.list_inflation_expectations(date_gte=...)`
Forward-looking inflation expectations (TIPS-derived breakeven rates).

### Federal Funds Rate — `client.list_fed_funds_rate(date_gte=...)`
Effective federal funds rate, daily.

## Workflow recipes

### Recipe: Yield curve inversion alert
```python
import pandas as pd
yields = list(client.list_treasury_yields(date_gte="2024-01-01"))
df = pd.DataFrame([{
    "date": y.date,
    "yield_2y": y.yield_2_year,
    "yield_10y": y.yield_10_year,
    "spread": y.yield_10_year - y.yield_2_year,
} for y in yields])
df["inverted"] = df["spread"] < 0
inversion_days = df[df["inverted"]]
print(f"Yield curve inverted on {len(inversion_days)} days in this period")
```

### Recipe: Real rate computation for DCF
```python
# Latest 10Y treasury - latest inflation expectation = real rate
yields = next(iter(client.list_treasury_yields()))  # latest
inflation = next(iter(client.list_inflation_expectations()))
real_rate = yields.yield_10_year - inflation.value_10_year
print(f"10Y real rate: {real_rate:.2%}")
```

### Recipe: Macro regime classifier
```python
fed = next(iter(client.list_fed_funds_rate()))
cpi = next(iter(client.list_inflation()))
spread = next(iter(client.list_treasury_yields())).yield_10_year - next(iter(client.list_treasury_yields())).yield_2_year

if spread < 0 and fed.value > 4:
    regime = "late_cycle_tightening"
elif cpi.value > 3 and fed.value < 4:
    regime = "behind_the_curve"
else:
    regime = "neutral"
```

## Plan tier

Economy endpoints are included in all Stocks plans (Basic free, Starter $29, Developer $79, Advanced $199). No separate macro subscription required.
