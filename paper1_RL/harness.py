"""
================================================================================
 ΠΕΙΡΑΜΑΤΙΚΟ ΕΡΓΑΛΕΙΟ για το αρθρο -- πραγματικα δεδομενα S&P500 (2013-2018)
================================================================================
 Τρεχει RRL agent σε οποιοδηποτε ticker, με επιλεγομενο:
   - reward:   'der' (entropic) η 'dsr' (differential Sharpe)
   - theta:    risk aversion (μονο για der)
   - features: 'returns' | 'ta' | 'volume' | 'all'
 Αυστηρα: causal features, standardize train-only, out-of-sample, multi-seed.

 Yahoo ΕΙΝΑΙ ΚΛΕΙΣΤΟ στο sandbox -> χρησιμοποιουμε cached πραγματικο S&P500.
 (Στον υπολογιστη σου: αντικαταστησε το load_ticker με yfinance.download.)
"""
import numpy as np, pandas as pd
import autograd.numpy as anp
from autograd import grad
from autograd.scipy.special import logsumexp

_DF=None
def load_ticker(ticker):
    """Πραγματικα OHLCV απο cached S&P500. Επιστρεφει close, volume, returns."""
    global _DF
    if _DF is None: _DF=pd.read_csv('sp500_5yr.csv')
    s=_DF[_DF.Name==ticker].sort_values('date')
    if len(s)<300: raise ValueError(f'{ticker}: {len(s)} days (too few)')
    close=s.close.to_numpy(float); vol=s.volume.to_numpy(float)
    ret=np.diff(close)/close[:-1]
    return close[1:], vol[1:], ret           # aligned με ret

# ---------- causal features ----------
def _ema(x,n):
    a=2/(n+1); o=np.zeros_like(x); o[0]=x[0]
    for i in range(1,len(x)): o[i]=a*x[i]+(1-a)*o[i-1]
    return o
def _rsi(c,n=14):
    d=np.diff(c,prepend=c[0]); up=np.clip(d,0,None); dn=-np.clip(d,None,0)
    return 100-100/(1+_ema(up,n)/(_ema(dn,n)+1e-9))
W=10
def make_X(close,vol,ret,kind):
    idx=np.arange(30,len(ret))
    def ta(i):
        c=close[:i+1]; r14=_rsi(c)[-1]/100
        e12=_ema(c,12)[-1]; e26=_ema(c,26)[-1]; macd=(e12-e26)/c[-1]
        ma20=c[-20:].mean(); sd20=c[-20:].std()+1e-9
        pctB=(c[-1]-(ma20-2*sd20))/(4*sd20); mom=(c[-1]-c[-W])/c[-W]
        return [r14,macd,pctB,mom,ret[i-W:i].std(),c[-1]/ma20-1]
    def volf(i):
        c=close[:i+1]; v=vol[:i+1]; sgn=np.sign(np.diff(c,prepend=c[0]))
        obv=np.cumsum(sgn*v); obvs=(obv[-1]-obv[-W])/(v[-W:].mean()*W+1e-9)
        vwap=(c[-W:]*v[-W:]).sum()/(v[-W:].sum()+1e-9)
        mf=(sgn[-W:]*v[-W:]).sum()/(v[-W:].sum()+1e-9)
        vz=(v[-1]-v[-W:].mean())/(v[-W:].std()+1e-9)
        return [obvs,c[-1]/vwap-1,mf,vz]
    parts=[]
    if kind in('returns','all','ta','volume'):
        if kind=='returns': parts=[ret[i-W:i] for i in idx]
        else:
            base=[ret[i-W:i] for i in idx]
            if kind in('ta','all'):     ta_=[ta(i) for i in idx]
            if kind in('volume','all'): vo_=[volf(i) for i in idx]
            parts=[]
            for k,i in enumerate(idx):
                row=list(base[k])
                if kind in('ta','all'): row+=ta_[k]
                if kind in('volume','all'): row+=vo_[k]
                parts.append(row)
    return np.array(parts,float), ret[idx]

# ---------- model + rewards ----------
def _tr(w,X,r,d):
    F=anp.tanh(anp.dot(X,w[:-1])+w[-1]); Fp=anp.concatenate([anp.array([0.0]),F[:-1]])
    return Fp*r-d*anp.abs(F-Fp)
def _der(w,X,r,d,th):
    R=_tr(w,X,r,d); return (1/th)*(logsumexp(-th*R)-anp.log(R.shape[0]))
def _dsr(w,X,r,d,th):
    R=_tr(w,X,r,d); return -(anp.mean(R)/(anp.std(R)+1e-9))
def _train(X,r,d,reward,th,seed,epochs=500,lr=0.05):
    rg=np.random.default_rng(seed); w=rg.normal(0,0.1,X.shape[1]+1)
    loss=_der if reward=='der' else _dsr
    g=grad(lambda w,X,r,d: loss(w,X,r,d,th)); m=np.zeros_like(w); v=np.zeros_like(w)
    for ep in range(1,epochs+1):
        gr=np.clip(g(w,X,r,d),-5,5); m=0.9*m+0.1*gr; v=0.999*v+0.001*gr**2
        w=w-lr*(m/(1-0.9**ep))/(np.sqrt(v/(1-0.999**ep))+1e-8)
    return w
def _met(R,p=252):
    R=np.asarray(R); eq=np.cumprod(1+R); dn=R[R<0]
    return dict(ret=eq[-1]-1, sharpe=R.mean()/(R.std()+1e-9)*np.sqrt(p),
                sortino=R.mean()/(dn.std()+1e-9)*np.sqrt(p) if len(dn)>1 else np.nan,
                mdd=np.min(eq/np.maximum.accumulate(eq)-1))

def experiment(ticker, reward='der', theta=75.0, features='returns',
               delta=0.0005, seeds=range(4), train_frac=0.70, verbose=True):
    close,vol,ret=load_ticker(ticker)
    X,rN=make_X(close,vol,ret,features); split=int(train_frac*len(X))
    mu,sd=X[:split].mean(0),X[:split].std(0)+1e-9; Xs=(X-mu)/sd
    res=[]
    for s in seeds:
        w=_train(Xs[:split],rN[:split],delta,reward,theta,s)
        res.append(_met(np.asarray(_tr(w,Xs[split:],rN[split:],delta))))
    keys=['ret','sharpe','sortino','mdd']
    mean={k:np.nanmean([r[k] for r in res]) for k in keys}
    std ={k:np.nanstd ([r[k] for r in res]) for k in keys}
    bh=_met(rN[split:])
    if verbose:
        tag=f"{reward.upper()}" + (f"(θ={theta:g})" if reward=='der' else "")
        print(f"  {ticker:<6} {features:<8} {tag:<11} "
              f"ret {mean['ret']*100:>5.1f}±{std['ret']*100:>3.1f}%  "
              f"Sh {mean['sharpe']:>5.2f}±{std['sharpe']:>4.2f}  "
              f"So {mean['sortino']:>5.2f}  MDD {mean['mdd']*100:>5.1f}%   "
              f"[B&H ret {bh['ret']*100:>5.1f}% Sh {bh['sharpe']:.2f}]")
    return mean,std,bh

if __name__=="__main__":
    print("Πραγματικα δεδομενα S&P500 (2013-2018). Yahoo κλειστο στο sandbox.\n")
    print("=== ΔΟΚΙΜΗ 1: ιδιο ticker, διαφορα features (reward=DER, θ=75) ===")
    for f in ['returns','ta','volume','all']:
        experiment('AAPL', features=f)
    print("\n=== ΔΟΚΙΜΗ 2: DER vs DSR σε διαφορα assets (features=returns) ===")
    for tk in ['AAPL','XOM','GE','KO']:
        experiment(tk, reward='dsr')
        experiment(tk, reward='der', theta=75)
    print("\n=== ΔΟΚΙΜΗ 3: σαρωση theta σε καθοδικη μετοχη (GE) ===")
    for th in [25,75,150,300]:
        experiment('GE', reward='der', theta=th, features='returns')
