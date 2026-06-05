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

## 2. 🔴 Institutional connectors — OAuth πάνω σε ΥΠΑΡΧΟΝ paid account (όχι self-serve)

> **Επιβεβαιωμένο 2026-06-05:** το `/mcp` → S&P Global **δεν δίνει register** — το OAuth
> συνδέει υπάρχοντα S&P Global Capital IQ λογαριασμό, δεν είναι signup. Χωρίς institutional
> συνδρομή, **μη προσβάσιμο**. Το ίδιο για τους υπόλοιπους παρόχους παρακάτω.

| Source | Γιατί θα άξιζε | Πραγματική κατάσταση |
|---|---|---|
| **S&P Global / Capital IQ (Kensho)** | PiT consensus, estimate revisions, surprise, ιστορικό από 1996 — institutional-grade PEAD | 🔴 Θέλει **Capital IQ subscription**· το OAuth δεν εγγράφει. Όχι προσβάσιμο |
| **FactSet, Morningstar, Moody's, Pitchbook, LSEG, Daloopa, Aiera, Chronograph, Egnyte** | Estimates / fundamentals / transcripts | 🔴 OAuth πάνω σε paid account του παρόχου — δεν τα έχεις |
| **Interactive Brokers (IBKR)** | Multi-asset market data + execution | 🟡 Θέλει IBKR λογαριασμό (αν έχεις, self-serve signup διαθέσιμο) |
| **LunarCrush** | Social/sentiment (`stocks` tool) = ορθογώνια text modality | 🟡 Εκθέτει data tools + `auth`· LunarCrush έχει free/φθηνό tier — θέλει επιβεβαίωση |
| **Explorium** | Business / alternative data | 🟠 Metered / paid (`show-pricing-plans`) |

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

## Πρακτικό συμπέρασμα — ο ΡΕΑΛΙΣΤΙΚΟΣ δρόμος (αφού τα institutional είναι κλειστά)

Επειδή S&P Global / FactSet / Morningstar **δεν είναι προσβάσιμα** (θέλουν paid account),
ο τίμιος δρόμος αλλάζει: **δεν χρειάζεσαι analyst estimates για ένα πραγματικό PEAD.**

> **Key insight:** το κλασικό PEAD (Bernard-Thomas 1989· Foster-Olsen-Shevlin 1984) ορίζει
> το SUE με **seasonal random walk**, ΟΧΙ με analyst consensus:
> `SUE = (EPS_q − EPS_{q−4}) / σ(ΔEPS)`. Όλα τα συστατικά είναι **actuals** που υπάρχουν
> στο **SEC EDGAR** (PiT, με filing date). Έτσι παρακάμπτεται όλο το πρόβλημα estimates.

| Ανάγκη | Ρεαλιστική πηγή | Κατάσταση |
|---|---|---|
| Actuals (EPS ανά τρίμηνο) + filing dates | **SEC EDGAR** (companyconcept/companyfacts API) | 🟢 δωρεάν, PiT |
| **PEAD signal (SUE)** | seasonal-random-walk πάνω στα EDGAR actuals — **κανένα estimate** | 🟢 δωρεάν, PiT |
| Estimate-revisions signal (προαιρετικό 2ο) | FMP (φθηνό key) — όχι institutional | 🟠 key |
| **Survivorship-free universe** | Sharadar (ιστορικά μέλη δείκτη) ή as-traded constituent lists | 🟠 key — κανένα 🟢 δεν το λύνει πλήρως |
| Sentiment (ορθογώνιο σήμα) | LunarCrush + Hugging Face NLP πάνω σε Polygon news | 🟢/🟡 |

**Δύο highest-value actions (αναθεωρημένα):**
1. **SUE από SEC EDGAR** — το πρώτο πραγματικό, PiT, look-ahead-free PEAD σήμα με **μόνο
   δωρεάν data**. Αντικαθιστά τα Yahoo current-snapshot surprises (η αδυναμία του paper).
2. **Ένα Sharadar key** (~φθηνό) — το μόνο που λύνει το **survivorship bias** (§sec:alpha-oos
   caveat). Δευτερεύον αλλά απαραίτητο πριν από οποιοδήποτε alpha claim.

**Το μη-διαπραγματεύσιμο:** point-in-time + survivorship-controlled. Με EDGAR + Sharadar τα
έχεις και τα δύο — χωρίς institutional συνδρομή.
