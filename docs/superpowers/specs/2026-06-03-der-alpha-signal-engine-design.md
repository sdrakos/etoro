# Design: Signal Engine + DER Risk Layer — αναζήτηση alpha με Yahoo data

**Ημερομηνία:** 2026-06-03
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχετικό paper:** `paper1_RL/der_paper_full.tex`, §`sec:alpha` (Fundamental-Law decomposition)

## Στόχος

Το DER paper αποδεικνύει ότι το DER ελέγχει το risk αλλά **δεν** παράγει alpha — το
alpha πρέπει να έρθει από νέα **ορθογώνια πληροφορία** (§`sec:signal`, §`sec:alpha`).
Η §`sec:alpha` ορίζει το πλαίσιο: `IR = IC·√BR·TC`, με αρχιτεκτονική «signal engine
(IC + breadth) wrapped by DER (risk/transfer layer)» και κλείνει με την παραδοχή ότι
*«confirmation requires a longer sample and strict walk-forward validation»*.

Αυτό το έργο παραδίδει ακριβώς αυτή την επιβεβαίωση: φέρνει **νέα ορθογώνια σήματα**
από δωρεάν Yahoo data, τα περνά από το **Fundamental-Law gate** (`ic_analysis.py`), και
αποδεικνύει την αρχιτεκτονική σε **longer/stressed walk-forward (2015-2024, incl. 2020 +
2022 crashes)**.

## Μη-στόχοι (YAGNI)

- **Δεν** μαθαίνουμε το directional σήμα. Το paper απέδειξε ότι learning → overfit
  (§`sec:signal`). Μόνο fixed, theory-driven signs.
- **Δεν** χρησιμοποιούμε historical fundamentals (PE/PB/ROE). Το yfinance δίνει μόνο
  current snapshot → σοβαρό look-ahead. Tier-3 value overlay εκτός scope.
- **Δεν** αλλάζουμε το `trader/` package ούτε το `back/`. Επαναχρησιμοποιούμε μόνο τον
  δοκιμασμένο bar-fetch (`trader/data/sources/yahoo.py`).
- **Δεν** αλλάζουμε τον υπάρχοντα DER κώδικα/θεωρία· τον εφαρμόζουμε ως risk layer.
- **Δεν** χτίζουμε production trading system· research-grade reproducible scripts.

## Αρχιτεκτονική — hybrid

Επαναχρησιμοποιούμε τον bar+cache layer του `trader/` για OHLCV (ήδη δοκιμασμένος),
προσθέτουμε μικρό Yahoo "extras" fetcher στο `paper1_RL/`, και κρατάμε τα experiments
ως numpy scripts στο στυλ των υπαρχόντων reproducibility scripts του paper.

```
paper1_RL/
  yahoo_research_data.py   # ΝΕΟ — fetch & cache universe data σε offline-reproducible μορφή
  ic_analysis.py           # ΥΠΑΡΧΟΝ (user-added) — γενικεύεται σε shared "alpha gate"
  pead_experiment.py       # ΝΕΟ — (A) PEAD / earnings-surprise drift
  sector_mom_vol_der.py    # ΝΕΟ — (B) sector-neutral momentum + VIX-driven θ
  all_levers_v3.py         # ΥΠΑΡΧΟΝ — pattern αναφοράς για metrics M() & combos
```

## Components

### 1. `yahoo_research_data.py` — shared data layer

Κατεβάζει μία φορά και κρατά σε cache (npz/parquet, offline-reproducible όπως το paper):

- **`close_mat`, `vol_mat`** (T×N adjusted daily) + `dates` index + `tickers` list.
  Reuse `trader.data.sources.yahoo.fetch_bars` για συνέπεια με το repo.
- **Earnings**: ανά ticker, `get_earnings_dates` → (date, EPS Estimate, Reported EPS,
  Surprise%). Επιβεβαιωμένο: ~50 τρίμηνα ιστορικό ως 2014.
- **Sector map**: `Ticker.info['sector']` ανά ticker → dict ticker→sector.
- **`^VIX`**: daily Close series, aligned στο `dates` index.

**Universe**: fixed list ~150 liquid large caps (από S&P 500 / Nasdaq-100). Το survivorship
bias **καταγράφεται ρητά** ως limitation (συνεπές με την επιλογή "test first" στο rigor).
Window: 2015-01-01 → 2024-12-31.

**Interface**: `load_universe() -> dict` με keys `close, vol, dates, tickers, earnings,
sector, vix`. Cache-aside: αν υπάρχει το cache file, δεν ξανακατεβάζει.

### 2. `ic_analysis.py` — Fundamental-Law alpha gate (γενίκευση)

Σήμερα τρέχει σε hardcoded `close_mat.npy` (2013-2018, 470 stocks) με 5 fixed signals.
Γενικεύεται ώστε:

- Να φορτώνει το νέο Yahoo universe μέσω `yahoo_research_data.load_universe()`.
- Να δέχεται **signal callable** (π.χ. `pead_surprise`, `sector_neutral_mom`) πέρα από τα
  built-in price signals.
- Να επιστρέφει το ίδιο dict: `IC, IC_t, predIR, realIR, TC, ls_ann` (Πίνακας `tab:ic`).

**Acceptance criterion (gate)**: ένα σήμα προωθείται σε strategy backtest μόνο αν
`IC_t > 2` ξεχωριστά **ή** βελτιώνει το combined `IC_t`/`realIR`. Αλλιώς απορρίπτεται
ρητά (καμία αξίωση alpha).

### 3. `pead_experiment.py` — (A) PEAD directional alpha

- **Signal**: για κάθε stock/μέρα, το πιο πρόσφατο post-earnings Surprise% εντός drift
  window (+1…+60 trading days μετά την ανακοίνωση)· 0 εκτός window.
  Cross-sectionally z-scored ανά μέρα.
- **No look-ahead**: entry **T+1** μετά την earnings date (η ανακοίνωση είναι γνωστή μόνο
  μετά το close της ημέρας ανακοίνωσης).
- **Gate**: τρέχει μέσα από `ic_analysis` → IC, t-stat, pred/real IR, TC.
- **Strategy** (αν περάσει gate): long top-decile θετικό surprise / short bottom-decile,
  market-neutral, net 5bps· DER risk overlay (vol-target) από πάνω.
- **Output**: νέα γραμμή στον `tab:ic` + Sharpe/Sortino/MaxDD walk-forward vs equal-weight.

### 4. `sector_mom_vol_der.py` — (B) sector-neutral momentum + VIX-driven θ

Επέκταση της λογικής του `all_levers_v3.py`:

- **Sector-neutral 12-1 momentum**: demean το momentum **εντός sector** (όχι global).
  Εξουδετερώνει το momentum-crash (Daniel-Moskowitz) — τον failure mode που αναφέρει το
  paper. Risk-parity-ish weighting.
- **VIX-driven θₜ** (practical state-dependent θ): scale exposure αντιστρόφως ανάλογα με
  το VIX regime (`θ_t ↑` όταν VIX ψηλά → de-risk πριν την αναταραχή). Operationalizes το
  roadmap item #2 του paper (§`sec:future`).
- **Gate**: το sector-neutral momentum περνά από `ic_analysis`.
- **Comparison** (walk-forward 2015-2024): plain momentum → sector-neutral → sector-neutral
  + VIX-θ. Report stand-alone **και** combined-with-market (roadmap item #3, §`sec:future`).

### Evaluation (κοινό)

- Επαναχρήση του `M()` metrics pattern (`all_levers_v3.py:18`): ret, Sharpe, Sortino, MDD.
- Strictly walk-forward: **70/30 chronological split** (default, συνεπές με το paper
  §`sec:method`)· report **μόνο** OOS test metrics.
- Paired Wilcoxon όπου συγκρίνουμε per-asset (ίδιο με `backtest.py`).
- Stressed sub-period analysis: 2020 Q1 (COVID) + 2022 (bear) ξεχωριστά.

## Data flow

```
yahoo_research_data.load_universe()
        │  close, vol, dates, tickers, earnings, sector, vix
        ▼
  ┌─────────────────────────────────────────────┐
  │  ic_analysis.py  (Fundamental-Law GATE)       │
  │  signal → IC, t-stat, predIR, realIR, TC      │
  └─────────────────────────────────────────────┘
        │ IC_t > 2 ?  (αλλιώς reject, no alpha claim)
        ├── pead_surprise ──────► pead_experiment.py ──► tab:ic row + WF metrics
        └── sector_neutral_mom ─► sector_mom_vol_der.py ─► tab:ic row + WF metrics
                                          │
                                          ▼
              combined signal engine wrapped by DER (§sec:alpha architecture)
                                          │
                                          ▼
                  (C) academic-paper-writer → extends §sec:alpha
```

## Honest caveats (baked-in, συνεπή με το ύφος του paper)

1. **Survivorship bias**: universe = current constituents → documented ρητά ως limitation.
2. **Fundamental Law είναι gate, όχι εγγύηση**: κανένα alpha claim χωρίς `IC_t > 2` OOS.
3. **Free-data IC είναι μικρό** (~0.02-0.05). Ο μοχλός είναι breadth + risk control, όχι
   signal genius. Αναμενόμενο realized IR ~0.3-0.8 στην καλύτερη, market-neutral.
4. **No learning** του directional σήματος — fixed theory-driven signs μόνο.
5. **Earnings estimate** από yfinance είναι τρέχον consensus (πιθανώς revised) — limitation
   καταγράφεται· το Surprise% παραμένει το κλασικό PEAD signal.

## (C) Write-up

Τα αποτελέσματα γράφονται ως **επέκταση της §`sec:alpha`** (νέες γραμμές στον `tab:ic` για
PEAD + sector-neutral momentum, walk-forward 2015-2024, stressed validation 2020/2022) μέσω
του `academic-paper-writer` skill. Δεν δημιουργείται αποκομμένη ενότητα.

## Σειρά υλοποίησης

1. `yahoo_research_data.py` (data layer — προαπαιτούμενο όλων)
2. Γενίκευση `ic_analysis.py` (gate)
3. (A) `pead_experiment.py`
4. (B) `sector_mom_vol_der.py`
5. (C) write-up μέσω `academic-paper-writer`
