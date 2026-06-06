"""Generate all publication figures for paper4 in one consistent style.
Runs the honest nested ML once (~3-5 min) and the static-data ablations, saving
paper4/figures/fig_*.png at publication quality."""
from __future__ import annotations
import os, sys, json, warnings
from datetime import datetime, timezone
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from etf_data import load_etf_matrix
from features import build_features
from dmn import nested_walkforward
from ts_momentum import build_ts_weights
from costs import net_returns
from metrics import ann_ir

sys.path.insert(0, os.path.abspath(os.path.join("..", "..", "Strategies", "slow-momentum-fast-reversion")))
from signals import zscore_xs, xs_weights   # cross-sectional baseline (the negative)

FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))

# ---- consistent publication style (serif to match LaTeX Computer Modern) ----
plt.rcParams.update({
    "font.family": "serif", "font.size": 12, "axes.titlesize": 13,
    "axes.labelsize": 12, "legend.fontsize": 10, "figure.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.3, "savefig.bbox": "tight",
})
GREEN, RED, BLUE, ORANGE, GRAY = "#2a7f4f", "#c0392b", "#1f4e9c", "#e08a1e", "#888888"


def _ffill(c):
    c = c.copy()
    for j in range(c.shape[1]):
        last = np.nan
        for i in range(len(c)):
            if np.isnan(c[i, j]): c[i, j] = last
            else: last = c[i, j]
    return c


def _scale(r, target=0.10):
    return r * (target / (r.std() * np.sqrt(252) + 1e-12))


def cross_sectional_ir(close, dates, score_kind, from_year=2017):
    """Net-of-cost OOS IR of a dollar-neutral cross-sectional equity book (the 'negative').
    Keeps NaNs (zscore_xs / xs_weights ignore them) so late-IPO names don't truncate the
    panel; realistic equity costs (spread + 300bps borrow); measured from `from_year`."""
    close = _ffill(close)
    yr = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc).year for m in dates])
    f0 = np.where(yr == from_year - 1)[0][-1]
    T, N = close.shape; warm = 252
    fwdTN = np.zeros((T, N)); fwdTN[:-1] = np.nan_to_num(close[1:] / close[:-1] - 1.0)
    W = np.zeros((T, N))
    for t in range(warm, T - 1):
        with np.errstate(all="ignore"):
            s = (zscore_xs(close[t - 21] / close[t - 252] - 1.0) if score_kind == "mom"
                 else zscore_xs(close[t] / close[t - 21] - 1.0))
        W[t] = xs_weights(np.where(np.isfinite(s), s, np.nan), max(N // 10, 2))
    net = net_returns(W, fwdTN, spread_bps=5.0, short_fin_bps_annual=300.0)
    return ann_ir(net[f0:T - 1])


def ts_rules_ir(close):
    close = _ffill(close); v = ~np.isnan(close).any(1); close = close[v]
    T, N = close.shape
    W = build_ts_weights(close); fwdTN = np.zeros((T, N)); fwdTN[:-1] = close[1:] / close[:-1] - 1.0
    return ann_ir(net_returns(W, fwdTN, spread_bps=5.0, short_fin_bps_annual=0.0)[252:T - 1])


def sharpe_corr(close):
    close = _ffill(close); v = ~np.isnan(close).any(1); close = close[v]
    T, N = close.shape
    W = build_ts_weights(close); fwdTN = np.zeros((T, N)); fwdTN[:-1] = close[1:] / close[:-1] - 1.0
    # spread-only (short_fin=0) to match the headline ETF cost model and isolate the
    # diversification (correlation) effect, not the equity-borrow cost.
    net = net_returns(W, fwdTN, spread_bps=5.0, short_fin_bps_annual=0.0)[252:T - 1]; r = _scale(net)
    ret = np.vstack([np.zeros((1, N)), close[1:] / close[:-1] - 1.0])[252:]
    cc = np.corrcoef(ret.T); avgc = (cc.sum() - N) / (N * (N - 1))
    return r.mean() / r.std() * np.sqrt(252), avgc


def main():
    close, dates, tickers = load_etf_matrix()
    T, N = close.shape
    years = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc).year for m in dates])
    d = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc) for m in dates])

    # ===== honest nested ML =====
    X, fwd = build_features(close)
    f1 = np.where(years == 2016)[0][-1]; f2 = np.where(years == 2020)[0][-1]
    POS, chosen, oos = nested_walkforward(X, fwd, [(f1, f2), (f2, T)], warm=252)
    ml_port = (POS * fwd).sum(0) / N
    ml_turn = np.zeros(T); ml_turn[1:] = np.abs(POS[:, 1:] - POS[:, :-1]).sum(0) / N
    ml = _scale((ml_port - 5e-4 * ml_turn)[oos])
    W = build_ts_weights(close); fwdTN = np.zeros((T, N)); fwdTN[:-1] = close[1:] / close[:-1] - 1.0
    ru = _scale(net_returns(W, fwdTN, spread_bps=5.0, short_fin_bps_annual=0.0)[oos])
    spy_r = np.concatenate([[0.0], close[1:, tickers.index("SPY")] / close[:-1, tickers.index("SPY")] - 1.0])[oos]
    do = d[oos]

    # ===== Fig 1: the motivating negative (all out-of-sample, same window as the table) =====
    zb = np.load("big_close.npz"); big = zb["close"]; bdates = zb["dates"]
    labels = ["Cross-sec equity\n(12-1 mom)", "Cross-sec equity\n(short trend)",
              "Time-series ETF\n(rules)", "Time-series ETF\n(ML LSTM)"]
    irs = [cross_sectional_ir(big, bdates, "mom"), cross_sectional_ir(big, bdates, "vel"),
           float(ann_ir(ru)), float(ann_ir(ml))]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.bar(labels, irs, color=[RED if x < 0 else GREEN for x in irs])
    ax.axhline(0, color="k", lw=.8); ax.set_ylabel("Information ratio (net, OOS 2017-2024)")
    ax.set_title("The momentum logic is dead cross-sectionally, alive on a diversified basket")
    for i, x in enumerate(irs): ax.text(i, x + (0.03 if x >= 0 else -0.08), f"{x:+.2f}", ha="center")
    ax.grid(axis="x", visible=False)
    fig.savefig(f"{FIG}/fig_negative.png"); plt.close(fig)

    # ===== Fig 2: ML vs rules vs SPY (OOS equity) =====
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.plot(do, 1e4 * np.cumprod(1 + spy_r), color=GRAY, lw=1.3, label="Buy & hold SPY")
    ax.plot(do, 1e4 * np.cumprod(1 + ru), color=ORANGE, lw=1.6, label="Rules time-series momentum")
    ax.plot(do, 1e4 * np.cumprod(1 + ml), color=BLUE, lw=2.2, label="ML LSTM Deep Momentum Network")
    ax.set_ylabel("Account value (EUR, start 10,000)"); ax.legend()
    ax.set_title("Out-of-sample (2016--2024), net of costs, scaled to 10\\% volatility".replace("\\%", "%"))
    fig.savefig(f"{FIG}/fig_ml_equity.png"); plt.close(fig)

    # ===== Fig 3: diversification (Sharpe vs correlation) =====
    import json as _json
    btk = _json.load(open("big_close.npz.json"))["tickers"]
    etk = tickers; ed = dates; bd = zb["dates"]
    common = sorted(set(bd.tolist()) & set(ed.tolist()))
    bi = {t: i for i, t in enumerate(bd)}; ei = {t: i for i, t in enumerate(ed)}
    stocks = [s for s in ["AAPL", "MSFT", "NVDA", "JPM", "GS", "XOM", "CVX", "JNJ", "UNH", "PG",
              "KO", "AMZN", "HD", "CAT", "BA", "NEE", "DUK", "LIN", "NEM", "GOOGL", "DIS", "AMT", "SPG"] if s in btk]
    divs = ["TLT", "IEF", "GLD", "DBC", "UUP"]

    def mat(names, src, idx, ticks):
        M = np.full((len(common), len(names)), np.nan)
        for j, nm in enumerate(names):
            col = ticks.index(nm)
            for r, ts in enumerate(common): M[r, j] = src[idx[ts], col]
        return M
    S = mat(stocks, big, bi, btk); D = mat(divs, close, ei, etk)
    sh_s, c_s = sharpe_corr(S); sh_d, c_d = sharpe_corr(D); sh_c, c_c = sharpe_corr(np.hstack([S, D]))
    names = ["22 sector\nstocks", "5 diversifiers\n(bonds/gold/...)", "27 combined"]
    sh = [sh_s, sh_d, sh_c]; cr = [c_s, c_d, c_c]
    fig, ax1 = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(3)
    ax1.bar(x - 0.2, sh, 0.4, color=BLUE, label="Sharpe (net)")
    ax1.set_ylabel("Sharpe ratio", color=BLUE); ax1.set_xticks(x); ax1.set_xticklabels(names)
    ax2 = ax1.twinx(); ax2.bar(x + 0.2, cr, 0.4, color=RED, label="avg pairwise corr"); ax2.grid(False)
    ax2.set_ylabel("avg pairwise correlation", color=RED)
    for i, s in enumerate(sh): ax1.text(i - 0.2, s + 0.01, f"{s:.2f}", ha="center", color=BLUE)
    for i, c in enumerate(cr): ax2.text(i + 0.2, c + 0.01, f"{c:.2f}", ha="center", color=RED)
    ax1.set_title("Diversity, not count: low correlation drives the risk-adjusted return")
    fig.savefig(f"{FIG}/fig_diversification.png"); plt.close(fig)

    # ===== Fig 4: beat buy & hold (return stacking) =====
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for r, nm, col, lw in [(spy_r, "Buy & hold SPY", GRAY, 1.4),
                            (0.5 * spy_r + 0.5 * ml, "50% SPY + 50% ML (no leverage)", GREEN, 1.6),
                            (spy_r + 0.5 * ml, "100% SPY + 50% ML overlay (1.5x)", RED, 2.4)]:
        ax.plot(do, 1e4 * np.cumprod(1 + r), color=col, lw=lw, label=nm)
    ax.set_ylabel("Account value (EUR, start 10,000)"); ax.legend()
    ax.set_title("Beating buy-and-hold by combining (return stacking), out-of-sample")
    fig.savefig(f"{FIG}/fig_beat_buyhold.png"); plt.close(fig)

    # ===== Fig 5: allocation in the 2022 selloff (long/short adaptation) =====
    W2 = build_ts_weights(close)
    t2022 = [t for t in range(252, T) if d[t].year == 2022 and d[t].month == 9][0]
    w = W2[t2022]; o = np.argsort(w)
    fig, ax = plt.subplots(figsize=(7.0, 5.5))
    ax.barh([tickers[j] for j in o], [w[j] for j in o],
            color=[GREEN if w[j] > 0 else RED for j in o])
    ax.axvline(0, color="k", lw=.8); ax.set_xlabel("portfolio weight (+ long / - short)")
    ax.set_title(f"Allocation in the 2022 selloff ({d[t2022].date()}): short risk, long USD/energy")
    fig.savefig(f"{FIG}/fig_alloc_2022.png"); plt.close(fig)

    print("ML configs:", chosen)
    print("Saved: fig_negative, fig_ml_equity, fig_diversification, fig_beat_buyhold, fig_alloc_2022")


if __name__ == "__main__":
    main()
