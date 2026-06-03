"""Figures για την §sec:alpha-oos (Yahoo 2015-2024 validation). Reproducible.
  alpha_gate_oos.png : IC/t-stat bar chart των 3 σηματων (γιατι απορριπτονται)
  sector_mom_oos.png : out-of-sample equity curves των στρατηγικων (B)
Reuse: yahoo_research_data, signals, alpha_gate (ολα tested). Numbers == tab:ic-oos/tab:strat-oos.
"""
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import yahoo_research_data as Y
import signals as S
from alpha_gate import evaluate
from pead_experiment import build_surprise_signal

d = Y.load_universe()
close = d["close"]; vix = d["vix"]
sec_map = d["sector"]; tickers = list(d["tickers"])
sectors = np.array([sec_map.get(t, "Unknown") for t in tickers])
T, N = close.shape
ret = np.zeros_like(close); ret[1:] = close[1:] / close[:-1] - 1

# --- σηματα ---
pead = build_surprise_signal(d)
mom = np.full((T, N), np.nan); smom = np.full((T, N), np.nan)
for t in range(252, T):
    m = S.momentum_12_1(close, t)
    mom[t] = S.zscore_xs(m)
    smom[t] = S.zscore_xs(S.sector_neutral(np.nan_to_num(m), sectors))

# ===== Figure 1: gate bar chart =====
sig = [("PEAD\nsurprise", pead), ("12-1\nmomentum", mom), ("sector-neutral\nmomentum", smom)]
res = [evaluate(signal=s, close=close, hold=21) for _, s in sig]
ts = [abs(r["IC_t"]) for r in res]; ics = [r["IC"] for r in res]
labels = [n for n, _ in sig]
colors = ["#16a34a" if t > 2 else "#dc2626" for t in ts]

fig, ax = plt.subplots(figsize=(7, 4.5))
bars = ax.bar(labels, ts, color=colors, alpha=0.8, edgecolor="k", lw=0.4)
ax.axhline(2.0, ls="--", c="k", lw=1.2)
ax.text(2.6, 2.05, "gate: |t| > 2", fontsize=9)
for b, ic, t in zip(bars, ics, ts):
    ax.text(b.get_x() + b.get_width()/2, t + 0.04, f"IC={ic:.3f}", ha="center", fontsize=9)
ax.set_ylabel("|IC t-stat|  (out-of-sample)")
ax.set_title("Fundamental-Law gate, Yahoo 2015–2024: all signals fail |t|>2")
ax.set_ylim(0, max(2.4, max(ts) + 0.4)); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("alpha_gate_oos.png", dpi=130); print("[saved] alpha_gate_oos.png")

# ===== Figure 2: out-of-sample equity curves =====
days = np.arange(252, T - 1); split = int(0.7 * len(days)); te = days[split:]
vix_ref = np.nanmedian(vix[:days[split]])
def port(s, use_vix):
    Rs = []
    for t in te:
        v = s[t]
        if np.isfinite(v).sum() < 10: Rs.append(0.0); continue
        w = np.nan_to_num(v); w = w / (np.nansum(np.abs(w)) + 1e-9)
        if use_vix: w = S.vix_theta_scale(w, vix[t], vix_ref)
        Rs.append(np.nansum(w * ret[t+1]) - 0.0005 * np.nansum(np.abs(w)))
    return np.array(Rs)

mkt = np.array([np.nanmean(ret[t+1]) for t in te])
R_ov = port(smom, True); L = min(len(mkt), len(R_ov))
curves = {
    "Market (long-only)":        (mkt, "#888", "--"),
    "Sector-neutral mom":        (port(smom, False), "#2563eb", "-"),
    "Sector-neutral + VIX-θ":    (R_ov, "#16a34a", "-"),
    "Market + overlay":          (0.7*mkt[:L] + 0.5*R_ov[:L], "#dc2626", "-"),
}
fig, ax = plt.subplots(figsize=(9, 5))
for name, (R, c, ls) in curves.items():
    eq = np.cumprod(1 + np.asarray(R))
    sh = np.mean(R)/(np.std(R)+1e-9)*np.sqrt(252)
    ax.plot(eq, label=f"{name} (Sh {sh:.2f})", color=c, ls=ls, lw=2)
ax.set_title("Out-of-sample equity, Yahoo 2015–2024 (incl. 2020 & 2022 stress)")
ax.set_xlabel("Days (test)"); ax.set_ylabel("Net asset value"); ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("sector_mom_oos.png", dpi=130); print("[saved] sector_mom_oos.png")
