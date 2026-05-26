# SEC Filings & Disclosures API Reference

8 endpoints for SEC EDGAR data, parsed and AI-ready. **This is a competitive differentiator** — most market data providers don't include parsed filings. Combine with Claude API for powerful LLM-driven research.

## Endpoints

### EDGAR Index — `client.list_filings_index(...)`
Master index of every SEC filing. Discovery layer.
```python
for f in client.list_filings_index(
    form_type="10-K",
    filing_date_gte="2024-01-01",
    filing_date_lte="2024-12-31",
):
    print(f.ticker, f.form_type, f.filing_date, f.accession_number, f.document_url)
```

**Filterable form types:**
- `10-K` (annual report), `10-Q` (quarterly)
- `8-K` (material events)
- `13-F` (institutional holdings, $100M+ AUM)
- `13-D` / `13-G` (5%+ ownership)
- `Form 3` (initial insider ownership)
- `Form 4` (insider transactions)
- `S-1` (IPO prospectus)
- `DEF 14A` (proxy statement)
- `SC 13D` (activist filings)

---

### 10-K Sections — `client.list_10k_sections(ticker)`
Plain-text Business + Risk Factors sections from annual reports. **AI-ready format** (cleaned, no HTML).
```python
for section in client.list_10k_sections(ticker="AAPL"):
    print(section.fiscal_year, section.section_name)
    print(section.text[:500])
```

**Sections typically returned:**
- Item 1: Business
- Item 1A: Risk Factors
- Item 7: MD&A

---

### 8-K Text — `client.list_8k_text(ticker)`
Parsed Items from 8-K filings.
```python
for filing in client.list_8k_text(ticker="TSLA"):
    print(filing.filing_date, filing.items)
    print(filing.text[:500])
```

**Common 8-K Items:**
- Item 1.01: Material agreement entered
- Item 2.02: Results of operations (earnings)
- Item 5.02: Departure/appointment of officers
- Item 7.01: Regulation FD disclosure
- Item 8.01: Other events

---

### 13-F Filings — `client.list_13f_filings(cik=..., ticker=...)`
Quarterly holdings of institutions managing >$100M.
```python
# Berkshire Hathaway holdings (CIK 0001067983)
for holding in client.list_13f_filings(cik="0001067983"):
    print(holding.period_of_report, holding.ticker, holding.shares, holding.market_value)
```

**Use cases:**
- Replicate hedge fund strategies (Berkshire, Bridgewater, Renaissance)
- Track activist positions (Pershing Square, Elliott Management)
- Identify smart-money rotations across sectors
- Find overlap between top investors

---

### Risk Factors — `client.list_risk_factors(ticker)`
Standardized, categorized risk disclosures. Uses Massive's published taxonomy.
```python
for rf in client.list_risk_factors(ticker="NVDA"):
    print(rf.category_primary, rf.category_secondary, rf.text[:200])
```
For methodology: see https://arxiv.org/pdf/2601.15247

---

### Risk Categories — `client.get_risk_categories()`
Full hierarchical taxonomy (primary → secondary → tertiary) for risk classification.

---

### Form 3 — `client.list_form_3(cik=..., ticker=...)`
Initial beneficial ownership when an insider first becomes subject to Section 16 reporting.

### Form 4 — `client.list_form_4(cik=..., ticker=...)`
**All changes** in insider ownership. Must be filed within 2 business days.
```python
for f4 in client.list_form_4(ticker="TSLA"):
    print(f4.transaction_date, f4.insider_name, f4.transaction_code,
          f4.shares, f4.price_per_share, f4.shares_owned_after)
```

**Transaction codes:**
- `P` = Open market purchase ← **bullish signal**
- `S` = Open market sale
- `A` = Grant/award (RSUs)
- `M` = Exercise of in-the-money derivatives
- `F` = Tax withholding
- `G` = Gift

---

## Workflow recipes

### Recipe: 13-F overlap between two hedge funds
```python
fund_a = {h.ticker for h in client.list_13f_filings(cik="0001067983")}  # Berkshire
fund_b = {h.ticker for h in client.list_13f_filings(cik="0001037389")}  # Renaissance
common = fund_a & fund_b
print(f"Both Berkshire and Renaissance hold: {common}")
```

### Recipe: Insider buying signal
```python
# Find open-market purchases (code P) above $100k in last 30 days
from datetime import date, timedelta
cutoff = (date.today() - timedelta(days=30)).isoformat()

signals = []
for ticker in ["AAPL", "MSFT", "NVDA", "TSLA"]:
    for f in client.list_form_4(ticker=ticker, filing_date_gte=cutoff):
        if f.transaction_code == "P":
            value = (f.shares or 0) * (f.price_per_share or 0)
            if value > 100_000:
                signals.append((ticker, f.insider_name, f.transaction_date, value))
signals.sort(key=lambda x: x[3], reverse=True)
```

### Recipe: LLM-powered 10-K risk analysis
```python
import anthropic
claude = anthropic.Anthropic()

sections = list(client.list_10k_sections(ticker="NVDA"))
risk_section = next((s for s in sections if "Risk" in s.section_name), None)

msg = claude.messages.create(
    model="claude-opus-4-5",
    max_tokens=2048,
    messages=[{"role": "user", "content": f"""
Analyze NVDA's risk factors. Identify:
1. New risks vs typical tech companies (what's unique)
2. Most concerning risks for thesis
3. Risks that have become more emphasized vs prior years

{risk_section.text[:30000]}
"""}],
)
print(msg.content[0].text)
```

### Recipe: M&A event detection from 8-K
```python
ma_signals = []
for f in client.list_8k_text(ticker=None, filing_date_gte="2024-01-01"):
    if "Item 1.01" in (f.items or []) or "merger" in (f.text or "").lower()[:1000]:
        ma_signals.append((f.ticker, f.filing_date, f.text[:200]))
```

### Recipe: Build a daily 8-K event feed
For event-driven strategies, watch 8-Ks as they're filed:
```python
from datetime import date
today = date.today().isoformat()
for f in client.list_filings_index(form_type="8-K", filing_date_gte=today):
    print(f.ticker, f.filing_date, f.document_url)
    # Fetch parsed text for relevant ones
    text = list(client.list_8k_text(ticker=f.ticker, filing_date=f.filing_date))
```

## Notes

- All filings included in all Stocks plans (no extra subscription)
- `accession_number` is the canonical SEC ID — use it for deduplication
- `document_url` points directly to SEC.gov for source verification
- For real-time event-driven trading: poll `list_filings_index` every few minutes during market hours
- Text fields can be **very long** (10-K Risk Factors often > 50,000 chars) — chunk for LLM processing
