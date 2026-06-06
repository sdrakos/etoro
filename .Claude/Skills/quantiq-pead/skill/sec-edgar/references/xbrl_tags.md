# Common us-gaap XBRL tags for quant signals

Companies tag inconsistently — always try fallbacks and verify with `available_tags(ticker)`.

## Earnings (PEAD / SUE, growth)
- `EarningsPerShareDiluted`, `EarningsPerShareBasic`, `EarningsPerShareBasicAndDiluted`
- `NetIncomeLoss`, `ProfitLoss`, `NetIncomeLossAvailableToCommonStockholdersBasic`
- `WeightedAverageNumberOfDilutedSharesOutstanding`, `WeightedAverageNumberOfSharesOutstandingBasic`

## Top line (growth, sales surprise)
- `RevenueFromContractWithCustomerExcludingAssessedTax` (most common post-2018)
- `Revenues`, `SalesRevenueNet`, `RevenueFromContractWithCustomerIncludingAssessedTax`

## Profitability / quality
- `GrossProfit`, `OperatingIncomeLoss`
- `CostOfRevenue`, `CostOfGoodsAndServicesSold`
- `ResearchAndDevelopmentExpense`, `SellingGeneralAndAdministrativeExpense`
- Margins = derive (GrossProfit / Revenue, OperatingIncomeLoss / Revenue).

## Balance sheet (value, leverage, quality)
- `Assets`, `AssetsCurrent`, `Liabilities`, `LiabilitiesCurrent`
- `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
- `LongTermDebtNoncurrent`, `LongTermDebt`, `DebtCurrent`
- `CashAndCashEquivalentsAtCarryingValue`

## Cash flow (quality, accruals)
- `NetCashProvidedByUsedInOperatingActivities`
- `NetCashProvidedByUsedInInvestingActivities`
- `PaymentsToAcquirePropertyPlantAndEquipment` (capex)
- Free cash flow = operating CF − capex (derive).
- Accruals = (NetIncomeLoss − operating CF) / Assets — a classic quality/earnings-management signal.

## Shares / dilution
- `CommonStockSharesOutstanding`, `EntityCommonStockSharesOutstanding` (dei)
- Buyback signal = YoY change in shares outstanding (fewer shares → bullish).

## Signal recipes (all from the above, all point-in-time)
- **PEAD / SUE**: seasonal-random-walk on `EarningsPerShareDiluted` (see `sue_pead.py`).
- **Earnings growth**: YoY % change in `NetIncomeLoss`.
- **Value**: `StockholdersEquity` / market cap (book-to-price); earnings yield = EPS / price.
- **Quality**: gross-profits-to-assets = `GrossProfit` / `Assets` (Novy-Marx).
- **Accruals**: (`NetIncomeLoss` − operating CF) / `Assets` (low accruals → higher quality).
- **Investment**: YoY asset growth (high growth → lower future returns — the investment factor).

Each becomes a column in a point-in-time daily panel (align on `filed`), then cross-sectionally
rank/standardize and combine with the others via risk parity. None of these is strong alone;
the edge (if any) is in combining several orthogonal ones — and surviving CPCV/DSR.
