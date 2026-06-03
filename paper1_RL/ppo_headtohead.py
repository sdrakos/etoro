"""
HEAD-TO-HEAD: DER-PPO vs CPPO (CVaR) vs risk-neutral PPO  --  Nasdaq-100 subset
================================================================================
 ΕΝΑΣ PPO πυρηνας (clipped surrogate, GAE-lite, shared per-asset Gaussian policy,
 long-only F_i in [0,1]). Αλλαζει ΜΟΝΟ το per-step reward ρ_t (το risk-objective):
   'pnl'  : ρ_t = R_t                       (risk-neutral PPO)
   'cvar' : ρ_t = R_t - β·max(0, L_t - VaR)  (CPPO, Rockafellar-Uryasev tail penalty)
   'der'  : ρ_t = DER_t (entropic)           (DER-PPO, η προταση)
 Portfolio: R_t = mean_i F_{i,t-1} r_{i,t} - δ·mean_i|ΔF|.  Αυστηρα out-of-sample.

 ΕΝΤΙΜΗ ΟΡΙΟΘΕΤΗΣΗ: οχι torch/SB3, οχι HF data, οχι LLM signals -> controlled
 re-implementation, οχι λεκτικη αναπαραγωγη του FinRL-DeepSeek. Universe = 55
 Nasdaq-100 ονοματα απο cached S&P500 (2013-2018).
"""
import numpy as np
import autograd.numpy as anp
from autograd import grad

SEED=2025
close=np.load('close_mat.npy'); idx=np.load('ndx_idx.npy')
C=close[:,idx]; T,N=C.shape
R_=np.zeros_like(C); R_[1:]=C[1:]/C[:-1]-1
W=8; days=np.arange(W,T-1)
# per-asset state: W recent returns ; target next-day return
Xa=np.stack([R_[d-W:d].T for d in days])      # (Dd, N, W)
rnext=R_[days+1]                               # (Dd, N)
Dd=len(days); split=int(0.7*Dd); DELTA=0.0005; GAMMA=0.99; SIG=0.5
# market state for critic: [mean recent ret, recent vol]
mkt=R_[:, :].mean(1)
ms=np.stack([[mkt[d-5:d].mean(), mkt[d-5:d].std()] for d in days])  # (Dd,2)

def sigm(z): return 1/(1+anp.exp(-z))
def expo(wa,X):                                # per-asset mean logit -> (Dd,N)
    return anp.einsum('dnw,w->dn', X, wa[:-1])+wa[-1]
def portfolio_R(F, rn):                         # F:(?,N) long-only [0,1]
    Fp=np.vstack([np.zeros((1,N)), F[:-1]])
    return (Fp*rn).mean(1)-DELTA*np.abs(F-Fp).mean(1)
def der_stream(R,theta=50.0,eta=0.05):
    M=np.exp(-theta*R[0]);out=np.zeros_like(R)
    for t in range(1,len(R)):
        Mn=(1-eta)*M+eta*np.exp(-theta*R[t]);out[t]=-(1/theta)*np.log(Mn/M);M=Mn
    return out
def cvar_stream(R,alpha=0.95,beta=4.0,win=60):
    L=-R; out=R.copy()
    for t in range(len(R)):
        lo=max(0,t-win); hist=L[lo:t+1]
        var=np.quantile(hist,alpha) if len(hist)>5 else 0.0
        out[t]=R[t]-beta*max(0.0,L[t]-var)     # penalize worst-tail losses (CVaR spirit)
    return out
def reward(R,kind):
    if kind=='pnl': return R
    if kind=='cvar': return cvar_stream(R)
    if kind=='der': return der_stream(R)
def metrics(R,p=252):
    R=np.asarray(R);eq=np.cumprod(1+R);dn=R[R<0]
    return dict(ret=eq[-1]-1, sh=R.mean()/(R.std()+1e-9)*np.sqrt(p),
                so=R.mean()/(dn.std()+1e-9)*np.sqrt(p) if len(dn)>1 else np.nan,
                mdd=float(np.min(eq/np.maximum.accumulate(eq)-1)))

def train(kind, seed=0, iters=160, K=4, lr=0.01, eps=0.2):
    rg=np.random.default_rng(seed)
    wa=rg.normal(0,0.1,W+1); wc=rg.normal(0,0.1,3)
    ma=np.zeros_like(wa);va=np.zeros_like(wa);mc=np.zeros_like(wc);vc=np.zeros_like(wc)
    Xtr=Xa[:split]; mstr=np.hstack([ms[:split],np.ones((split,1))])
    def Vf(wc): return anp.dot(mstr,wc)
    for it in range(1,iters+1):
        mu=np.asarray(expo(wa,Xtr))                       # (split,N)
        a=mu+SIG*rg.standard_normal(mu.shape)             # sample
        F=1/(1+np.exp(-a))                                # long-only [0,1]
        R=portfolio_R(F, rnext[:split]); rho=reward(R,kind)
        G=np.zeros_like(rho);acc=0.0
        for t in range(len(rho)-1,-1,-1): acc=rho[t]+GAMMA*acc;G[t]=acc
        V=np.asarray(Vf(wc)); Adv=G-V; Adv=(Adv-Adv.mean())/(Adv.std()+1e-8)
        oldlp=(-0.5*((a-mu)/SIG)**2).sum(1)               # old log-prob (per t, sum assets)
        def surr(wa):
            mu2=expo(wa,Xtr); lp=(-0.5*((a-mu2)/SIG)**2).sum(1)
            ratio=anp.exp(lp-oldlp)
            return -anp.mean(anp.minimum(ratio*Adv, anp.clip(ratio,1-eps,1+eps)*Adv))
        gA=grad(surr); gC=grad(lambda wc: anp.mean((G-Vf(wc))**2))
        for _ in range(K):
            ga=gA(wa); ma=0.9*ma+0.1*ga; va=0.999*va+0.001*ga**2
            wa=wa-lr*(ma/(1-0.9**it))/(np.sqrt(va/(1-0.999**it))+1e-8)
        gc=gC(wc); mc=0.9*mc+0.1*gc; vc=0.999*vc+0.001*gc**2
        wc=wc-lr*(mc/(1-0.9**it))/(np.sqrt(vc/(1-0.999**it))+1e-8)
    return wa
def evaluate(wa):
    mu=np.asarray(expo(wa,Xa[split:])); F=1/(1+np.exp(-mu)) # deterministic
    return metrics(portfolio_R_test(F))
def portfolio_R_test(F):
    return portfolio_R(F, rnext[split:])

if __name__=="__main__":
    import time
    bh=metrics(rnext[split:].mean(1))                     # equal-weight Nasdaq-100 subset
    print(f"PPO head-to-head | Nasdaq-100 subset ({N} ονοματα) | out-of-sample, 3 seeds\n")
    print(f"{'Strategy':<26}{'Return':>10}{'Sharpe':>9}{'Sortino':>9}{'MaxDD':>9}")
    print("-"*63)
    print(f"{'Equal-weight (B&H)':<26}{bh['ret']*100:>9.1f}%{bh['sh']:>9.2f}{bh['so']:>9.2f}{bh['mdd']*100:>8.1f}%")
    for kind,lbl in [('pnl','PPO (risk-neutral)'),('cvar','CPPO (CVaR)'),('der','DER-PPO (theta=50)')]:
        t0=time.time(); res=[evaluate(train(kind,seed=s)) for s in range(3)]
        m={k:np.mean([r[k] for r in res]) for k in ['ret','sh','so','mdd']}
        print(f"{lbl:<26}{m['ret']*100:>9.1f}%{m['sh']:>9.2f}{m['so']:>9.2f}{m['mdd']*100:>8.1f}%  ({time.time()-t0:.0f}s)")
    print("-"*63)
