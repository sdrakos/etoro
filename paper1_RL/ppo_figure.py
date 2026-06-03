"""Figure for the PPO head-to-head: test equity curves + compute-cost bars (English)."""
import numpy as np, time
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import ppo_headtohead as P

split=P.split; N=P.N; rn=P.rnext[split:]
def equity_and_time(kind,seed=0):
    t0=time.time(); wa=P.train(kind,seed=seed); dt=time.time()-t0
    mu=np.asarray(P.expo(wa,P.Xa[split:])); F=1/(1+np.exp(-mu))
    R=P.portfolio_R_test(F); return np.cumprod(1+R), dt, P.metrics(R)

bh_eq=np.cumprod(1+rn.mean(1))
curves={}; times={}; mdds={}
for kind in ['pnl','cvar','der']:
    eq,dt,m=equity_and_time(kind); curves[kind]=eq; times[kind]=dt; mdds[kind]=m['mdd']

fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,5),gridspec_kw={'width_ratios':[2,1]})
ax1.plot(bh_eq,label='Equal-weight B&H',color='#888',ls='--',lw=2)
ax1.plot(curves['pnl'],label='PPO (risk-neutral)',color='#2563eb',lw=2)
ax1.plot(curves['cvar'],label='CPPO (CVaR)',color='#16a34a',lw=2)
ax1.plot(curves['der'],label='DER-PPO',color='#dc2626',lw=2)
ax1.set_title('Out-of-sample equity (Nasdaq-100 subset, 55 names)')
ax1.set_xlabel('Days (test)'); ax1.set_ylabel('Net asset value'); ax1.legend(fontsize=9); ax1.grid(alpha=0.3)
# cost bars: training time (the commercial point: same risk control, lower cost)
labels=['CPPO\n(CVaR)','DER-PPO']
vals=[times['cvar'],times['der']]
bars=ax2.bar(labels,vals,color=['#16a34a','#dc2626'],alpha=0.85)
ax2.set_title('Training cost (lower is better)\nsame risk control')
ax2.set_ylabel('seconds')
for b,v in zip(bars,vals): ax2.text(b.get_x()+b.get_width()/2,v,f'{v:.0f}s',ha='center',va='bottom',fontsize=10)
plt.tight_layout(); plt.savefig('ppo_headtohead.png',dpi=130)
print('saved ppo_headtohead.png')
print('times:',{k:round(v,1) for k,v in times.items()},'MaxDD:',{k:round(v*100,1) for k,v in mdds.items()})
