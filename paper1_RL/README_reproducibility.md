# Differential Entropic Reward (DER) — Complete Package

Author: Stefanos Drakos (AGEL AI, Rhodes), ORCID 0000-0001-7417-2444
All experiments use real S&P 500 OHLCV (2013–2018), auto-downloaded from a public
GitHub mirror on first run. Seed 2025 throughout. No torch (numpy + autograd only).

================================================================================
 1. THE PAPER (publication-ready, English, pdflatex/Computer Modern)
================================================================================
  der_paper_full.pdf / .tex   13 pages — MAIN DELIVERABLE
        Full SOTA related work, theorem + proofs, Algorithm 1, risk-sensitive
        Bellman, 5 figures, 24 verified references. Sections:
        §1 Intro (+ "what prior work has done")
        §2 Related Work (RL-trading / risk measures / risk-sensitive RL / SOTA)
        §3 Problem formulation   §4 The DER (Thm 1, Prop 1–2, HJB, Algorithm 1)
        §5 Numerical verification (8/8)   §6 Methodology
        §7 Results (controlled, single-asset/regime, 48-stock backtest, ablations)
        §8 Architecture-agnostic: Actor–Critic + PPO head-to-head (DER-PPO vs CPPO)
        §9 Discussion   §10 Future Work (strategies, research-grounded)   §11 Conclusion
  der_paper.pdf / .tex        earlier 6-page version (superseded)

================================================================================
 2. THEORY VERIFICATION  (run first)
================================================================================
  verify_der_theory.py        8/8 PASS — checks C1–C6 two independent ways:
        C1 risk-neutral limit, C2 mean-variance, C3 cumulant expansion (err<1e-9),
        C4 telescoping, C5 risk-aversion asymmetry, C6 controlled example.

================================================================================
 3. EMPIRICAL CODE  (claim -> script)
================================================================================
  motivating_example.py   -> Fig 2 (equal Sharpe, opposite skew -> CE differs)
  backtest.py             -> Table 3 + Fig 3 + Wilcoxon p≈7e-15 (48 stocks, DER vs DSR)
  backtest_results.csv    -> per-stock backtest numbers
  harness.py              -> any single-asset run (ticker/reward/theta/features) + Table 2
  ta_features.py / ta_regime.py    -> technical-indicator ablation
  volume_signals.py       -> volume IC≈0 + redundancy (Section 7.4)
  volume_features.py      -> volume/order-flow feature test
  all_levers.py / _v2 / _v3.py     -> cross-sectional momentum + overlay -> Fig 4
  regime_experiment.py    -> regime-switching with crashes
  actor_critic_der.py     -> A2C transfer (DER MaxDD -3.8% vs -29.5% risk-neutral)
  ppo_headtohead.py       -> Table 4 (DER-PPO vs CPPO vs risk-neutral, Nasdaq-100)
  ppo_figure.py           -> Fig 5 (equity curves + training-cost bars)

================================================================================
 4. FIGURES (English labels)
================================================================================
  motivating.png  backtest_plots.png  all_levers_final.png  ppo_headtohead.png
  (also: equity.png, regime_equity.png, all_levers_equity.png)

================================================================================
 5. GREEK COMPANION (beginner theory primer)
================================================================================
  theoria_arxarioi.pdf / .tex   8-page Greek primer (RL + DER, intuition + full loop)
  notation_glossary.pdf / .tex  Greek symbol glossary (superseded by primer)
  tutorial_RL_trading.md        early beginner tutorial

DATA NOTE: Yahoo/Stooq are blocked in the sandbox; the cached S&P 500 set is used.
On your machine, swap load_ticker for yfinance to add fundamentals / VIX / 2020–2022.
