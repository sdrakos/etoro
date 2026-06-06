# Position Sizing & Portfolio Optimization — bibliography

References on optimal bet/position sizing and capital allocation, for maximizing the return of a
portfolio with predictive signals (relevant to paper4's diversified momentum book).

## Downloaded (PDF in folder)

| Paper | Topic | Why it matters here |
|-------|-------|---------------------|
| **Kelly (1956)** — A New Interpretation of Information Rate | Kelly criterion: growth-optimal bet size | the direct "maximize long-run profit" sizing rule |
| **Thorp (2006)** — The Kelly Criterion in Blackjack, Sports Betting and the Stock Market | Kelly applied to markets; fractional Kelly | practical, risk-aware leverage for our book |
| **Markowitz (1952)** — Portfolio Selection | mean-variance optimization | the classic capital-allocation framework |
| **Ledoit & Wolf (2004)** — Honey, I Shrunk the Sample Covariance Matrix | shrinkage covariance | robust covariance for allocation (fights estimation error) |
| **Moreira & Muir (2017)** — Volatility-Managed Portfolios | inverse-vol / regime sizing | the vol-scaling we already use |

## Paywalled (no free PDF — citation only; content covered by a held reference)

| Paper | Where the content is available |
|-------|--------------------------------|
| **Moody & Saffell (2001)** — Learning to Trade via Direct Reinforcement (IEEE TNN) | the direct-RL / differential-Sharpe sizing that **our LSTM loss implements**; cited in paper4 |
| **Grinold (1989)** — The Fundamental Law of Active Management (JPM) | covered by Grinold & Kahn, *Active Portfolio Management* (1999), cited in paper4 |
| **López de Prado (2016)** — Building Diversified Portfolios that Outperform (HRP, JPM) | covered in López de Prado, *Advances in Financial Machine Learning* (2018), cited in paper4 |

## The practical takeaway for our portfolio
- **Increase profit:** fractional Kelly leverage (Kelly/Thorp) — picks the growth-optimal leverage instead of the arbitrary 10% vol target; quarter/half-Kelly for safety.
- **Better allocation (raises Sharpe):** shrinkage covariance (Ledoit-Wolf) or HRP (López de Prado) instead of equal-capital.
- **Risk control:** volatility/regime targeting (Moreira-Muir) — already in use.
- **Honest caveat:** naive Kelly/mean-variance overfit and blow up; the robust variants (fractional, shrinkage, HRP) are the safe levers. Leverage raises return AND drawdown proportionally — Sharpe improves only via better allocation or a better signal.
