# Data Sources — Access Report (QuantIQ / DER)

**Ημερομηνία:** 2026-06-05 · **Σκοπός:** ποιες πηγές δεδομένων είναι όντως προσβάσιμες
για το επόμενο πραγματικό σήμα (PEAD / estimate-revisions / sentiment), με έμφαση στο
μη-διαπραγματεύσιμο: **point-in-time (PiT) + survivorship-controlled**.

Κατάσταση προσδιορίστηκε από τους MCP connectors που είναι συνδεδεμένοι στο session, τα
local skills, και το `back/.env` (single secrets store). Όπου εξαρτάται από login/tier,
σημειώνεται ρητά.

**Λεζάντα:** 🟢 Έτοιμο τώρα · 🟡 Connector υπάρχει, θέλει one-click auth (login) ·
🟠 Θέλει συνδρομή/key (μη ρυθμισμένο) · 🔴 Institutional / εκτός εμβέλειας

---

## 1. 🟢 Έτοιμα ΤΩΡΑ (key ή session ήδη ενεργό)

| Source | Πρόσβαση | Τι δίνει | PiT / Survivorship |
|---|---|---|---|
| **Massive / Polygon** | `MASSIVE_KEY` στο `back/.env` + `massive-api-skill` | Actuals, fundamentals, SEC filings, news/sentiment, corporate actions, short interest. **Όχι consensus estimates** | News timestamped (PiT-ish)· free tier ~2y / 5-calls-min |
| **SEC EDGAR** | Δωρεάν, μέσω `financial-analyst` skill | Earnings actuals + **ημερομηνία κατάθεσης** = PiT εξ ορισμού | ✅ PiT · ❌ survivorship |
| **Yahoo (yfinance)** | Δωρεάν, `trader/` + `value-stock-analyzer` | Prices, earnings surprise (current snapshot) | ❌ snapshot · ❌ survivorship — **η γνωστή αδυναμία του paper** |
| **Hugging Face** | Authenticated ως `sdrakos` (MCP) | NLP models + datasets για sentiment σε news/transcripts | n/a (modeling layer) |
| **eToro Public API** | `ETORO_*` keys στο `back/.env` + `etoro-api` skill | Prices/candles, portfolio, execution | Execution layer, όχι research estimates |

## 2. 🟡 Connector υπάρχει — θέλει μόνο login (one-click OAuth μέσω `/mcp`)

| Source | Γιατί αξίζει | Κατάσταση |
|---|---|---|
| **S&P Global / Capital IQ (Kensho)** ⭐ | **Το πιο πολύτιμο**: point-in-time consensus, estimate revisions, surprise, timestamp ανά αλλαγή, ιστορικό από 1996 — ακριβώς το PEAD/revisions institutional-grade | Connector = `kfinance.kensho.com`. Εκτίθεται **μόνο** ως `authenticate` → **όχι authed**. Auth = user-driven: `/mcp` → "claude.ai S&P Global" → browser authorize. **Το #1 action.** |
| **FactSet, Morningstar, Moody's, Pitchbook, LSEG, Daloopa, Aiera, Chronograph, Egnyte** | Estimates / fundamentals / transcripts institutional | Όλα μέσω `financial-analysis` plugin, **OAuth-gated**, όχι authed. Χρειάζεται login **και** λογαριασμό στον πάροχο |
| **Interactive Brokers (IBKR)** | Multi-asset market data + execution (cross-asset σήματα) | `authenticate` only → όχι authed |
| **LunarCrush** | Social/sentiment (έχει `stocks` tool) = ορθογώνια text modality | Εκθέτει data tools **και** `auth` — πιθανώς usable, θέλει επιβεβαίωση |
| **Explorium** | Business / alternative data | Tools εκτίθενται με `show-pricing-plans` / `estimate-cost` → **metered / paid** |

## 3. 🟠 Θέλουν συνδρομή / API key (ΔΕΝ είναι ρυθμισμένα)

| Source | Τι λύνει | Κόστος |
|---|---|---|
| **Sharadar** (Nasdaq Data Link) | **PiT fundamentals από 1990 + survivorship-free index membership από 1957** — λύνει ΚΑΙ τα δύο μη-διαπραγματεύσιμα | Προσιτό· χρειάζεται API key (δεν υπάρχει στο `.env`) |
| **FMP** (Financial Modeling Prep) | Analyst estimates + revisions (earnings momentum) | Φθηνό, με PiT caveats → θέλει επαλήθευση |
| **FRED** | Macro / cross-asset (rates, spreads, CPI) | Δωρεάν, θέλει free API key (ή public CSV) |

## 4. 🔴 Institutional / εκτός εμβέλειας
Bloomberg «Company Financials, Estimates and Pricing Point-in-Time» (2024), I/B/E/S
(διεθνείς earnings forecasts από 1971), Datastream, WRDS — ακριβά· μόνο αν το QuantIQ
φτάσει σε κλίμακα που τα δικαιολογεί.

---

## Πρακτικό συμπέρασμα — φθηνότερος τίμιος δρόμος για το πρώτο πραγματικό PEAD σήμα

| Ανάγκη | Πηγή | Κατάσταση |
|---|---|---|
| Actuals + ημερομηνίες ανακοίνωσης | SEC EDGAR ή Massive/Polygon | 🟢 διαθέσιμα |
| **Consensus estimates PiT** (το κενό) | **S&P Global** (αν το tier το δίνει) · αλλιώς Sharadar/FMP | 🟡 login · 🟠 key |
| **Survivorship-free universe** | Sharadar (ιστορικά μέλη δείκτη) | 🟠 key — κανένα 🟢 δεν το λύνει |
| Sentiment (2ο, ορθογώνιο σήμα) | LunarCrush + Hugging Face NLP πάνω σε Polygon news | 🟢/🟡 |

**Δύο highest-value actions:**
1. **Authenticate S&P Global** (`/mcp` → claude.ai S&P Global) — αποκαλύπτει αν το tier σου
   εκθέτει Capital IQ Estimates, που λύνει το δυσκολότερο: PiT consensus / revisions.
2. **Ένα Sharadar API key** — μόνο αυτό λύνει το **survivorship bias** που το DER paper
   παραδέχτηκε ως αδυναμία στα free data (§sec:alpha-oos caveats).

**Το μη-διαπραγματεύσιμο:** ό,τι κι αν επιλεγεί → **point-in-time + survivorship-controlled**.
Αυτά τα δύο ξεχωρίζουν ένα πραγματικό σήμα από ένα backtest-φάντασμα.
