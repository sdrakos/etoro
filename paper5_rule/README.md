# paper5_rule

QUANTIQ trading model. Follow the `ai-trading` skill pipeline:
source paper -> reproduce/critique -> evolve on Yahoo -> honest leak-free backtest -> eToro engine (demo) -> journal paper -> business report (report_GR.tex).

Layout: `code/` (features, models, sizing, metrics), `engine/` (cli, adapter, etoro_backtest), `figures/`, `paper/`, `report_GR.tex`.

## Status

Scaffold only. Plan: follow the `ai-trading` skill pipeline here with the **rule strategy**
(time-series momentum + volatility targeting + no-trade band), the production-viable core proven on
real eToro prices (+10.2%/yr, IR 1.53). To be developed later: reproduce -> evolve (BOCPD brake,
multi-horizon, vol-target dial) -> honest eval -> eToro engine -> paper/report.
