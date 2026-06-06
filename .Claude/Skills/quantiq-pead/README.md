# QuantIQ — PEAD & Cross-Firm Lead-Lag (project bundle)

Πλήρες πακέτο: το `sec-edgar` skill (δεδομένα + σήματα) **μαζί** με τα modules αξιολόγησης,
τον orchestrator πραγματικών δεδομένων, και το εκπαιδευτικό υλικό.

## Δομή
```
quantiq-pead/
├── skill/
│   ├── sec-edgar/            πηγαία μορφή του skill (επεξεργάσιμη)
│   │   ├── SKILL.md
│   │   ├── scripts/          edgar_client, fundamentals_loader, sue_pead, combine_signals
│   │   └── references/       endpoints.md, xbrl_tags.md
│   └── sec-edgar.skill       έτοιμο πακέτο για ανέβασμα στα Skills
├── analysis/
│   ├── pead_event_study.py   own-firm PEAD: drift profile, half-life, durability, persistence
│   ├── leadlag_event_study.py cross-firm (same-industry) lead-lag, Fama-MacBeth
│   ├── run_pead_real.py      orchestrator: EDGAR→SUE + price panel + event study
│   ├── README_pead_real.md   runbook πραγματικών δεδομένων
│   └── belief_state_p0_runner.py  Belief-State P0 walk-forward harness (Kalman→ridge)
├── docs/
│   ├── pead_tutorial_GR.pdf  φροντιστήριο μαθηματικών (αρχάριοι)
│   ├── pead_tutorial_GR.tex
│   ├── Methodology_GR_signal_extraction.pdf
│   └── methodology_signal_in_noise.md
└── results/                  δείγματα synthetic εξόδων (PNG/JSON) — validation, όχι αγορά
```

## Εξαρτήσεις
```
pip install pandas numpy requests matplotlib
# για το φροντιστήριο .tex: xelatex + DejaVu Serif (ήδη compiled στο docs/)
```

## Πώς κουμπώνουν (ροή)
```
EDGAR (data.sec.gov)
   │  edgar_client + fundamentals_loader        [skill]
   ▼
quarterly EPS (point-in-time, filed dates)
   │  sue_pead.compute_sue                       [skill]
   ▼
own-firm SUE events ───────────────┐
   │                               │
   │ leadlag_event_study           │ pead_event_study / run_pead_real
   │ (peers from SIC)              ▼
   ▼                         own-PEAD signal + drift/half-life/durability
peer lead-lag signal ──────────────┤
                                    ▼
                       combine_signals (risk parity / ERC)   [skill]
                                    ▼
                          τελικό cross-sectional σκορ
```

## Σειρά εκτέλεσης (στο μηχάνημά σου — το sandbox μπλοκάρει data.sec.gov)
1. **Έλεγχοι χωρίς δίκτυο** (αποδεικνύουν ότι η μηχανή δουλεύει):
   ```
   python analysis/run_pead_real.py --selftest
   python analysis/leadlag_event_study.py --selftest
   python analysis/belief_state_p0_runner.py        # synthetic Belief-State P0
   ```
2. **Πραγματικά δεδομένα own-PEAD:** δες `analysis/README_pead_real.md` (prices.csv, tickers,
   User-Agent, προαιρετικό sectors.csv).
3. **Lead-lag:** φτιάξε `group_map = build_sic_map(user_agent, tickers)` και κάλεσε
   `run(prices, events, group_map)` από το `leadlag_event_study.py`.
4. **Συνδυασμός:** πέρασε τα signal frames στο `combine_signals.combine({...}, method="erc")`.

## Δύο κανόνες που κρατούν το backtest τίμιο
- **Point-in-time:** χρησιμοποίησε τη `filed` ημερομηνία του EDGAR και είσοδο **T+1** — ποτέ το period end.
- **Survivorship:** universe **as-traded** (μέλη όπως ήταν κάθε χρονιά), όχι τα σημερινά μέλη δείκτη.

## Τίμια προσδοκία
Σε free δεδομένα τα σήματα είναι **αδύναμα και πιθανότατα φθίνοντα** (όπως ήδη φάνηκε στο DER).
Το alpha (αν υπάρχει) έρχεται από τον **συνδυασμό** πολλών ορθογώνιων σημάτων με risk parity —
όχι από ένα μόνο. Ένα μέτριο αποτέλεσμα ή ένα καθαρό null με σωστά Newey-West t-stats είναι
σωστό και δημοσιεύσιμο.
```
```
```
*Τα αρχεία στο `results/` είναι synthetic validation outputs — δείχνουν ότι τα εργαλεία μετρούν
σωστά (ανακτούν γνωστή αλήθεια), ΟΧΙ αποτελέσματα αγοράς.*
```
