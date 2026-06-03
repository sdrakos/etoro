"""
ACTOR-CRITIC (A2C) + DER  --  το reward μπαινει σε proper actor-critic, οχι RRL.
================================================================================
 Actor:  stochastic Gaussian policy πανω στο pre-tanh logit -> θεση F_t=tanh(a_t)
 Critic: V(x_t) (γραμμικο) εκτιμα το value· advantage A_t = G_t - V(x_t)
 Reward variants (per-step ρ_t):
    'return' : R_t                      (risk-neutral baseline)
    'dsr'    : Differential Sharpe       (Moody-Saffell baseline)
    'der'    : Differential Entropic     (η προταση -> risk-sensitive critic)
 A2C update (autograd):
    actor  loss = -mean( logπ(a_t) * A_t_detached )  - β*entropy
    critic loss =  mean( (G_t - V(x_t))^2 )
 Δοκιμη σε regime data ΜΕ crashes (εκει μετραει το ρισκο), αυστηρα out-of-sample.
"""
import numpy as np
import autograd.numpy as anp
from autograd import grad

SEED=2025; rng=np.random.default_rng(SEED)

# ---------- data: regime με crashes ----------
def regime(n=4000):
    r=np.empty(n); s=0
    for t in range(n):
        if s==0:
            r[t]=rng.normal(0.0006,0.007)
            if rng.random()<0.015: s=1
        else:
            r[t]=rng.normal(-0.004,0.020)+0.015*rng.standard_t(3)
            if rng.random()<0.12: s=0
    return r
ret=regime(); 
W=8
X=np.array([ret[i-W:i] for i in range(W,len(ret)-1)])
rnext=ret[W+1:len(ret)]                       # align: x_t -> r_{t+1}
D=len(X); split=int(0.7*D); DELTA=0.0005; GAMMA=0.99; SIGMA=0.4

# ---------- per-step rewards (numpy, given positions F) ----------
def trading_returns(F):
    Fp=np.concatenate([[0.0],F[:-1]])
    return F*rnext[:len(F)]*0+Fp*rnext[:len(F)]-DELTA*np.abs(F-Fp)  # R_t=F_{t-1} r_t - cost
def reward_stream(R, kind, theta=50.0, eta=0.05):
    if kind=='return': return R.copy()
    if kind=='der':
        M=np.exp(-theta*R[0]); out=np.zeros_like(R)
        for t in range(1,len(R)):
            Mn=(1-eta)*M+eta*np.exp(-theta*R[t]); out[t]=-(1/theta)*np.log(Mn/M); M=Mn
        return out
    if kind=='dsr':
        A=0.0;B=1e-6;out=np.zeros_like(R)
        for t in range(len(R)):
            dA=R[t]-A; dB=R[t]**2-B; den=(B-A**2)**1.5+1e-9
            out[t]=(B*dA-0.5*A*dB)/den; A+=eta*dA; B+=eta*dB
        return out
    raise ValueError

# ---------- model ----------
def actor_mu(wa,X): return anp.dot(X,wa[:-1])+wa[-1]          # pre-tanh mean
def critic_V(wc,X): return anp.dot(X,wc[:-1])+wc[-1]
def metrics(R,p=252):
    R=np.asarray(R);eq=np.cumprod(1+R);dn=R[R<0]
    return dict(ret=eq[-1]-1, sh=R.mean()/(R.std()+1e-9)*np.sqrt(p),
                mdd=float(np.min(eq/np.maximum.accumulate(eq)-1)))

def train(kind, theta=50.0, epochs=400, lr=0.02, seed=0):
    rg=np.random.default_rng(seed)
    wa=rg.normal(0,0.1,W+1); wc=rg.normal(0,0.1,W+1)
    ma=np.zeros_like(wa);va=np.zeros_like(wa);mc=np.zeros_like(wc);vc=np.zeros_like(wc)
    Xtr=X[:split]; 
    gA=grad(lambda wa,a,A: -anp.mean(logp(wa,Xtr,a)*A))      # actor loss
    gC=grad(lambda wc,G: anp.mean((G-critic_V(wc,Xtr))**2))  # critic loss
    for ep in range(1,epochs+1):
        mu=actor_mu(wa,Xtr)                                  # numpy via autograd-compatible
        mu=np.asarray(mu)
        a=mu+SIGMA*rg.standard_normal(len(mu))               # sample pre-tanh action
        F=np.tanh(a)
        R=np.empty(len(F)); Fp=0.0
        for t in range(len(F)): R[t]=Fp*rnext[t]-DELTA*abs(F[t]-Fp); Fp=F[t]
        rho=reward_stream(R,kind,theta)                      # per-step reward
        # discounted returns G_t
        G=np.zeros(len(rho)); acc=0.0
        for t in range(len(rho)-1,-1,-1): acc=rho[t]+GAMMA*acc; G[t]=acc
        V=np.asarray(critic_V(wc,Xtr)); Adv=G-V
        Adv=(Adv-Adv.mean())/(Adv.std()+1e-8)
        # actor step
        ga=gA(wa,a,Adv); ma=0.9*ma+0.1*ga; va=0.999*va+0.001*ga**2
        wa=wa-lr*(ma/(1-0.9**ep))/(np.sqrt(va/(1-0.999**ep))+1e-8)
        # critic step
        gc=gC(wc,G); mc=0.9*mc+0.1*gc; vc=0.999*vc+0.001*gc**2
        wc=wc-lr*(mc/(1-0.9**ep))/(np.sqrt(vc/(1-0.999**ep))+1e-8)
    return wa
def logp(wa,X,a):                                            # Gaussian log-prob of pre-tanh a
    mu=actor_mu(wa,X); return -0.5*((a-mu)/SIGMA)**2 - anp.log(SIGMA)-0.5*anp.log(2*anp.pi)

def evaluate(wa):
    mu=np.asarray(actor_mu(wa,X[split:])); F=np.tanh(mu)     # deterministic at test
    R=np.empty(len(F));Fp=0.0
    for t in range(len(F)): R[t]=Fp*rnext[split+t]-DELTA*abs(F[t]-Fp); Fp=F[t]
    return metrics(R)

if __name__=="__main__":
    import time
    bh=metrics(rnext[split:])
    print(f"Actor-Critic (A2C) σε regime data ΜΕ crashes | out-of-sample\n")
    print(f"{'Reward':<22}{'Return':>10}{'Sharpe':>9}{'MaxDD':>9}")
    print("-"*50)
    print(f"{'Buy & Hold':<22}{bh['ret']*100:>9.1f}%{bh['sh']:>9.2f}{bh['mdd']*100:>8.1f}%")
    for kind,lbl in [('return','A2C risk-neutral'),('dsr','A2C + DSR'),('der','A2C + DER (th=50)')]:
        t0=time.time()
        res=[evaluate(train(kind,seed=s)) for s in range(3)]
        m={k:np.mean([r[k] for r in res]) for k in ['ret','sh','mdd']}
        print(f"{lbl:<22}{m['ret']*100:>9.1f}%{m['sh']:>9.2f}{m['mdd']*100:>8.1f}%   ({time.time()-t0:.0f}s)")
    print("-"*50)
