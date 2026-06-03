"""Figure 3 (backtest_plots.png) απο το backtest_results.csv.
Left: κατανομη max drawdown (DER vs DSR). Right: per-asset Sharpe DER vs DSR.
(Ο plotter ηταν ad-hoc στο αρχικο sandbox· εδω ρητος & reproducible.)"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

df = pd.read_csv('backtest_results.csv')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

# Left: distribution of max drawdown
bins = np.linspace(-0.55, 0.0, 24)
ax1.hist(df.dsr_mdd, bins=bins, alpha=0.6, color='#2563eb', label=f'DSR (worst {df.dsr_mdd.min()*100:.0f}%)')
ax1.hist(df.der_mdd, bins=bins, alpha=0.7, color='#dc2626', label=f'DER (worst {df.der_mdd.min()*100:.0f}%)')
ax1.axvline(-0.20, ls='--', c='k', lw=1, alpha=0.6)
ax1.set_xlabel('Maximum drawdown'); ax1.set_ylabel('# assets')
ax1.set_title(f'Max drawdown across {len(df)} equities (OOS)'); ax1.legend(); ax1.grid(alpha=0.3)

# Right: per-asset Sharpe DER vs DSR
lim = [min(df.dsr_sh.min(), df.der_sh.min()) - 0.2, max(df.dsr_sh.max(), df.der_sh.max()) + 0.2]
ax2.scatter(df.dsr_sh, df.der_sh, s=28, c='#16a34a', alpha=0.7, edgecolor='k', lw=0.3)
ax2.plot(lim, lim, ls='--', c='k', lw=1, alpha=0.6)
ax2.set_xlim(lim); ax2.set_ylim(lim)
ax2.set_xlabel('DSR Sharpe'); ax2.set_ylabel('DER Sharpe')
ax2.set_title(f'Per-asset Sharpe (DER > DSR in {100*np.mean(df.der_sh>df.dsr_sh):.0f}%)'); ax2.grid(alpha=0.3)

plt.tight_layout(); plt.savefig('backtest_plots.png', dpi=130)
print('[saved] backtest_plots.png')
