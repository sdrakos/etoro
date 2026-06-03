"""
QuantIQ — THEORETICAL ALPHA TEST (Fundamental Law of Active Management)
================================================================================
 Πριν το production: μετρα το IC καθε σηματος, βαλε το στον νομο IR=IC*sqrt(BR)*TC,
 και συγκρινε προβλεπομενο (upper bound) vs realized IR. Δειχνει ΑΝ υπαρχει alpha.
   IC  = cross-sectional corr(signal_t , forward_return_t)  -> skill
   BR  = N_stocks * rebalances/yr (ανεξαρτητα στοιχηματα, optimistic)
   TC  = realized_IR / predicted_IR  (ποσο χανεται σε υλοποιηση/κοστη)
 Realized = long-short decile portfolio (top-bottom), net of 5bps, OOS.
 Δεδομενα: real S&P500 (2013-2018, 470 μετοχες). Καθαρα out-of-sample.
"""
import numpy as np, json
close=np.load('close_mat.npy')                 # (T, Nstocks)
T,N=close.shape
R=np.zeros_like(close); R[1:]=close[1:]/close[:-1]-1
HOLD=21                                          # monthly rebalance / forward window
DELTA=0.0005
dates=np.arange(252, T-HOLD, HOLD)              # need 252d lookback, HOLD fwd
split=int(0.7*len(dates)); oos=dates[split:]    # out-of-sample rebalance dates

def signal(name, t):
    if name=='mom_12_1':  return close[t-21]/close[t-252]-1          # 12m skip last month
    if name=='reversal_1m': return -(close[t]/close[t-21]-1)         # short-term reversal
    if name=='low_vol':   return -R[t-60:t].std(0)                   # low-vol anomaly
    if name=='mom_6_1':   return close[t-21]/close[t-126]-1          # 6m momentum
    if name=='trend_50_200': return close[t]/close[t-200]-1          # long trend
def fwd_ret(t): return close[t+HOLD]/close[t]-1                      # forward HOLD-day return

def zscore(x):
    m=np.nanmean(x); s=np.nanstd(x)+1e-9; return (x-m)/s

def analyze(name):
    ics=[]; ls_returns=[]
    for t in oos:
        s=signal(name,t); f=fwd_ret(t)
        ok=np.isfinite(s)&np.isfinite(f)
        if ok.sum()<50: continue
        s_,f_=s[ok],f[ok]
        ics.append(np.corrcoef(zscore(s_),f_)[0,1])
        # long-short decile portfolio (equal weight), net of costs
        k=max(5,int(0.1*len(s_))); order=np.argsort(s_)
        longs=order[-k:]; shorts=order[:k]
        ls=f_[longs].mean()-f_[shorts].mean()-2*DELTA
        ls_returns.append(ls)
    ic=np.array(ics); ls=np.array(ls_returns)
    icbar=ic.mean(); icstd=ic.std()
    rebs_per_yr=252/HOLD
    # Fundamental Law: breadth = N independent bets per year (optimistic upper bound)
    BR=N*rebs_per_yr
    predicted_IR=icbar*np.sqrt(BR)                          # upper bound (TC=1)
    realized_IR=ls.mean()/(ls.std()+1e-9)*np.sqrt(rebs_per_yr)
    TC=realized_IR/predicted_IR if predicted_IR!=0 else 0
    t_ic=icbar/(icstd+1e-9)*np.sqrt(len(ic))               # is IC significant?
    return dict(IC=icbar, IC_t=t_ic, predIR=predicted_IR, realIR=realized_IR, TC=TC,
                ls_ann=ls.mean()*rebs_per_yr)

if __name__=="__main__":
    print("QuantIQ — Theoretical Alpha Test | Fundamental Law | OOS, real S&P500\n")
    print(f"{'Signal':<14}{'IC':>8}{'IC t-stat':>11}{'pred IR':>9}{'real IR':>9}{'TC':>7}{'LS ann':>9}")
    print("-"*68)
    res={}
    for nm in ['mom_12_1','mom_6_1','reversal_1m','low_vol','trend_50_200']:
        r=analyze(nm); res[nm]=r
        print(f"{nm:<14}{r['IC']:>8.3f}{r['IC_t']:>11.1f}{r['predIR']:>9.2f}{r['realIR']:>9.2f}{r['TC']:>7.2f}{r['ls_ann']*100:>8.1f}%")
    # combined signal: equal-weight z-score of significant signals
    print("-"*68)
    def combo(t):
        zs=[zscore(np.where(np.isfinite(signal(n,t)),signal(n,t),np.nan)) for n in ['mom_12_1','reversal_1m','low_vol']]
        return np.nanmean(np.vstack(zs),0)
    ics=[]; ls=[]
    for t in oos:
        s=combo(t); f=fwd_ret(t); ok=np.isfinite(s)&np.isfinite(f)
        if ok.sum()<50: continue
        s_,f_=s[ok],f[ok]; ics.append(np.corrcoef(s_,f_)[0,1])
        k=max(5,int(0.1*len(s_)));o=np.argsort(s_)
        ls.append(f_[o[-k:]].mean()-f_[o[:k]].mean()-2*DELTA)
    ic=np.array(ics);ls=np.array(ls);reb=252/HOLD
    pIR=ic.mean()*np.sqrt(N*reb); rIR=ls.mean()/(ls.std()+1e-9)*np.sqrt(reb)
    print(f"{'COMBINED':<14}{ic.mean():>8.3f}{ic.mean()/(ic.std()+1e-9)*np.sqrt(len(ic)):>11.1f}{pIR:>9.2f}{rIR:>9.2f}{rIR/pIR if pIR else 0:>7.2f}{ls.mean()*reb*100:>8.1f}%")
    print("-"*68)
    print("IC t-stat>2 => στατιστικα σημαντικο σημα. realIR = πραγματικο alpha (Sharpe-like).")
