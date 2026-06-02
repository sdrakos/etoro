# paper1_RL/sector_mom_vol_der.py
"""(B) Sector-neutral 12-1 momentum + VIX-driven θ (state-dependent DER risk).
Compare: plain mom -> sector-neutral -> sector-neutral + VIX-θ. Walk-forward OOS.
Report stand-alone ΚΑΙ combined-with-market (paper §sec:future roadmap #3)."""
import numpy as np
import yahoo_research_data as Y
import signals as S
from alpha_gate import evaluate, passes

def metrics(R, p=252):
    R = np.asarray(R); eq = np.cumprod(1 + R); dn = R[R < 0]
    return dict(ret=eq[-1]-1, sh=R.mean()/(R.std()+1e-9)*np.sqrt(p),
                so=(R.mean()/(dn.std()+1e-9)*np.sqrt(p)) if len(dn) > 1 else np.nan,
                mdd=np.min(eq/np.maximum.accumulate(eq)-1), eq=eq, R=R)

def main():
    d = Y.load_universe()
    close = d["close"]; vix = d["vix"]
    sec_map = d["sector"]                                # {ticker: sector}
    tickers = list(d["tickers"])
    sectors = np.array([sec_map.get(t, "Unknown") for t in tickers])
    T, N = close.shape
    ret = np.zeros_like(close); ret[1:] = close[1:] / close[:-1] - 1

    # build daily momentum + sector-neutral momentum signal matrices
    mom = np.full((T, N), np.nan); smom = np.full((T, N), np.nan)
    for t in range(252, T):
        m = S.momentum_12_1(close, t)
        mom[t] = S.zscore_xs(m)
        smom[t] = S.zscore_xs(S.sector_neutral(np.nan_to_num(m), sectors))

    # gate και για τα δυο
    for name, sig in [("plain 12-1 mom", mom), ("sector-neutral mom", smom)]:
        r = evaluate(signal=sig, close=close, hold=21)
        tag = "PASS" if passes(r) else "reject"
        print(f"[gate] {name:<22} IC={r['IC']:.4f} t={r['IC_t']:.2f} "
              f"realIR={r['realIR']:.2f} -> {tag}")

    # walk-forward portfolios
    days = np.arange(252, T - 1); split = int(0.7 * len(days)); te = days[split:]
    vix_ref = np.nanmedian(vix[:days[split]])
    def port(sig, use_vix):
        Rs = []
        for t in te:
            s = sig[t]
            if np.isfinite(s).sum() < 10: Rs.append(0.0); continue
            w = np.nan_to_num(s); w = w / (np.nansum(np.abs(w)) + 1e-9)
            if use_vix: w = S.vix_theta_scale(w, vix[t], vix_ref)
            Rs.append(np.nansum(w * ret[t+1]) - 0.0005 * np.nansum(np.abs(w)))
        return np.array(Rs)

    mkt = np.array([np.nanmean(ret[t+1]) for t in te])
    res = {
        "Market (long-only)":        metrics(mkt),
        "Plain mom":                 metrics(port(mom, False)),
        "Sector-neutral mom":        metrics(port(smom, False)),
        "Sector-neutral + VIX-θ":    metrics(port(smom, True)),
    }
    R_ov = res["Sector-neutral + VIX-θ"]["R"]; L = min(len(mkt), len(R_ov))
    res["Market + overlay"] = metrics(0.7*mkt[:L] + 0.5*R_ov[:L])

    print(f"\n{'Strategy':<26}{'Return':>9}{'Sharpe':>9}{'Sortino':>9}{'MaxDD':>9}")
    print("-"*62)
    for k, m in res.items():
        print(f"{k:<26}{m['ret']*100:>8.1f}%{m['sh']:>9.2f}{m['so']:>9.2f}{m['mdd']*100:>8.1f}%")

    # stressed sub-periods (2020 COVID & 2022 bear): worst 60-day MaxDD στο OOS
    print("\nStressed check (worst 60-day MaxDD στο OOS):")
    for k in ["Market (long-only)", "Sector-neutral + VIX-θ"]:
        R = res[k]["R"]
        worst = min(np.min(np.cumprod(1+R[i:i+60])/np.maximum.accumulate(np.cumprod(1+R[i:i+60]))-1)
                    for i in range(0, max(1, len(R)-60), 10))
        print(f"  {k:<26}{worst*100:>8.1f}%")

if __name__ == "__main__":
    main()
