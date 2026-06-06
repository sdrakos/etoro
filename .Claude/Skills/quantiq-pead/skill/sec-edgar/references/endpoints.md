# EDGAR endpoints & access rules (cheat-sheet)

## Base
- API base: `https://data.sec.gov/`
- Ticker→CIK map: `https://www.sec.gov/files/company_tickers.json` (note: `www.sec.gov`, not `data.sec.gov`)
- No API key, no registration. JSON responses.

## Access rules (non-negotiable)
- **User-Agent header required**, with a real name + email (e.g. `Stefanos Drakos stefanos@agelai.gr`). Missing/blank → `403`.
- **Rate limit: ≤10 requests/second** across all your machines. Excessive load → IP block. The client throttles to ~8 rps and backs off on `403/429/5xx`.
- CIK must be **10 digits, zero-padded** in endpoint URLs (Apple `320193` → `CIK0000320193`).

## Endpoints
| Purpose | URL pattern | Notes |
|---|---|---|
| All facts for a company | `/api/xbrl/companyfacts/CIK##########.json` | One big JSON; every concept the firm ever tagged |
| One concept over time | `/api/xbrl/companyconcept/CIK##########/{taxonomy}/{tag}.json` | Efficient when you need a single line item (e.g. EPS) |
| Filing history + dates | `/submissions/CIK##########.json` | form, filingDate, accessionNumber, primaryDocument… |
| One fact across all firms | `/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json` | Cross-sectional snapshot. Period: `CY2023Q4` (duration) or `CY2023Q4I` (instant) |

Taxonomies: `us-gaap` (most line items), `dei` (entity info), `srt`, `ifrs-full`.

## Fact record fields (inside `units`)
Each fact has: `end` (period end), `start` (for durations), `val`, `fy`, `fp` (`Q1..Q3`,`FY`), `form` (`10-Q`,`10-K`,`8-K`,`20-F`…), `accn` (accession), `filed` (**filing date — your point-in-time stamp**), sometimes `frame`.

## Bulk (avoid hammering the API)
- `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` — all Company Facts/Frames data.
- `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip` — all filing histories.
Download once, parse locally, when you need many companies.

## Gotchas (these cause silent, wrong results)
1. **Use `filed`, not `end`, for backtests.** A Q4 2023 number filed 2024-02-01 was NOT knowable on 2023-12-31. Aligning on `end` injects look-ahead.
2. **Tag inconsistency.** Not everyone uses `Revenues`; many use `RevenueFromContractWithCustomerExcludingAssessedTax`. Call `available_tags()` or use the fallback lists in `fundamentals_loader.py`.
3. **Duplicates / amendments.** The same `end` appears multiple times (restatements, different fiscal contexts). Decide: earliest `filed` (as-first-reported → correct for event timing) vs latest (restated). The client's `keep=` controls this.
4. **XBRL history starts ~2009–2011.** Structured facts exist for large filers from 2009, all filers by 2011. Earlier data is only HTML/text in the Archives, not these JSON endpoints.
5. **Q4 EPS is not filed as a quarter.** Derive it: FY (10-K) − (Q1+Q2+Q3). EPS is only approximately additive; for rigor use `NetIncomeLoss` ÷ diluted shares.
6. **Survivorship.** EDGAR has delisted firms too, but if you build a universe from *today's* index members you reintroduce survivorship bias. Use an as-traded constituent list.
7. **`company_tickers.json` is on `www.sec.gov`.** The client sets the right `Host` header for it automatically.
