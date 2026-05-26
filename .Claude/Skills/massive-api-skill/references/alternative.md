# Alternative Data API Reference

2 endpoints covering news + sentiment. The news endpoint is the most heavily used data source for LLM-powered trading and research workflows.

## Endpoints

### News — `client.list_ticker_news(ticker=..., ...)`
Articles + sentiment + extracted tickers from financial news.

```python
for n in client.list_ticker_news("NVDA", order="desc", limit=100):
    print(n.published_utc)
    print(n.title)
    print(n.publisher.name, "→", n.article_url)
    print("Sentiment:", n.sentiment, "—", n.sentiment_reasoning)
    print("Tickers mentioned:", n.tickers)
    print("---")
```

**Available filters:**
- `ticker` — single ticker filter (omit for all news)
- `published_utc_gte` / `published_utc_lte` — date range
- `order` — `asc` or `desc`
- `limit` — max 1000 per page
- `sort` — `published_utc` (default)

**Fields per article:**
- `id`, `publisher` (name, homepage, logo, favicon), `title`, `author`
- `published_utc`, `article_url`, `tickers` (list extracted from content)
- `image_url`, `description`, `keywords`
- `insights[]` per ticker:
  - `ticker`, `sentiment` (positive/negative/neutral), `sentiment_reasoning`

### Sentiment Analytics — aggregated sentiment scores (partner endpoint)
Roll-up sentiment over time windows for a ticker.

---

## Workflow recipes

### Recipe: Daily news digest with sentiment scores
```python
from datetime import date, timedelta
yesterday = (date.today() - timedelta(days=1)).isoformat()

news = list(client.list_ticker_news(
    ticker="TSLA",
    published_utc_gte=yesterday,
    order="desc",
    limit=100,
))

positive = sum(1 for n in news for i in (n.insights or []) if i.ticker == "TSLA" and i.sentiment == "positive")
negative = sum(1 for n in news for i in (n.insights or []) if i.ticker == "TSLA" and i.sentiment == "negative")
net = positive - negative
print(f"TSLA net sentiment yesterday: {net} ({positive}+ / {negative}-)")
```

### Recipe: Combine with Claude API for qualitative analysis
```python
import anthropic
news = list(client.list_ticker_news("NVDA", limit=20))
headlines = "\n".join(f"- {n.title}" for n in news)

claude = anthropic.Anthropic()
msg = claude.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Analyze these recent NVDA headlines for thesis-relevant catalysts:\n{headlines}"}],
)
print(msg.content[0].text)
```

### Recipe: News-driven event scanner across watchlist
```python
watchlist = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN"]
events = []
for ticker in watchlist:
    for n in client.list_ticker_news(ticker, limit=20, order="desc"):
        # Look for high-impact keywords
        keywords = ["acquisition", "earnings beat", "guidance", "FDA", "lawsuit", "downgrade", "upgrade"]
        if any(k in (n.title or "").lower() for k in keywords):
            events.append((ticker, n.title, n.sentiment, n.published_utc))
events.sort(key=lambda x: x[3], reverse=True)
```

### Recipe: Quantify news flow as feature
For PEAD / news-momentum strategies, count news volume + average sentiment as features:
```python
from collections import defaultdict
from datetime import datetime

news_features = defaultdict(lambda: {"count": 0, "pos": 0, "neg": 0, "neu": 0})
for n in client.list_ticker_news(ticker="TSLA", limit=1000):
    day = datetime.fromisoformat(n.published_utc.replace("Z", "+00:00")).date()
    news_features[day]["count"] += 1
    for i in (n.insights or []):
        if i.ticker == "TSLA":
            news_features[day][i.sentiment[:3]] += 1

# news_features now usable as daily features for backtests
```

## Notes

- News goes back several years (depends on plan)
- Sentiment is computed automatically by Massive's NLP pipeline — use it as a baseline but verify with Claude for nuance
- The `tickers` field is auto-extracted — may have false positives for common words that match tickers (e.g., "A" → Agilent)
- For backtesting: be careful of **look-ahead bias** — use `published_utc` strictly, not `acquired_utc`
