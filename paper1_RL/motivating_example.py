"""
ΕΛΕΓΧΟΜΕΝΟ ΠΕΙΡΑΜΑ -- γιατι χρειαζομαστε το DER.
Δυο σειρες αποδοσεων με ΙΔΙΟ μεσο & ΙΔΙΑ διακυμανση, αλλα:
  * "Healthy"  : θετικη ασυμμετρια (σπανια μεγαλα κερδη)
  * "Crash-prone": αρνητικη ασυμμετρια + παχιες ουρες (σπανια μεγαλα crash)
Το Sharpe τις βαθμολογει ΙΔΙΑ. Το entropic CE (DER) ξεχωριζει τον κινδυνο ουρας.
"""
import numpy as np
from scipy import stats

rng = np.random.default_rng(7)
N = 4000

# --- Crash-prone: 97% ηρεμες μερες + 3% crashes ---
calm   = rng.normal(0.0008, 0.006, N)
crash_mask = rng.random(N) < 0.03
crash  = np.where(crash_mask, rng.normal(-0.05, 0.02, N), 0.0)
bad = calm + crash

# --- Healthy: καθρεφτης (σπανια μεγαλα ΚΕΡΔΗ αντι για crash) ---
calm2  = rng.normal(0.0008, 0.006, N)
jump_mask = rng.random(N) < 0.03
jump   = np.where(jump_mask, rng.normal(0.05, 0.02, N), 0.0)
good = calm2 + jump

# --- Επιβαλλουμε ΑΚΡΙΒΩΣ ιδιο μεσο & std (affine) ωστε Sharpe ταυτοσημο ---
def match(x, mu_t, sd_t):
    return (x - x.mean())/x.std()*sd_t + mu_t
TARGET_MU, TARGET_SD = 0.0008, 0.012
good = match(good, TARGET_MU, TARGET_SD)
bad  = match(bad,  TARGET_MU, TARGET_SD)

def sharpe(x):  return x.mean()/x.std()*np.sqrt(252)
def CE(x, th):  return -(1/th)*np.log(np.mean(np.exp(-th*x)))   # entropic certainty equiv.

print(f"{'':<14}{'mean':>10}{'std':>9}{'skew':>9}{'kurt':>9}{'Sharpe':>9}")
print("-"*60)
for name,x in [("Healthy",good),("Crash-prone",bad)]:
    print(f"{name:<14}{x.mean():>10.5f}{x.std():>9.5f}"
          f"{stats.skew(x):>9.2f}{stats.kurtosis(x):>9.2f}{sharpe(x):>9.3f}")

print("\nEntropic Certainty Equivalent CE_theta (οσο μεγαλυτερο, τοσο καλυτερο):")
print(f"{'theta':>8}{'CE Healthy':>14}{'CE Crash':>14}{'διαφορα':>12}")
print("-"*48)
for th in [10,50,100,200]:
    cg,cb = CE(good,th), CE(bad,th)
    print(f"{th:>8}{cg:>14.5f}{cb:>14.5f}{(cg-cb):>12.5f}")

# --- Plot ---
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,4.6))
ax1.hist(good,bins=80,alpha=0.6,label="Healthy (+skew)",color="#16a34a",density=True)
ax1.hist(bad, bins=80,alpha=0.6,label="Crash-prone (-skew, fat tails)",color="#dc2626",density=True)
ax1.axvline(good.mean(),color="k",ls="--",lw=1)
ax1.set_title(f"Same mean & std = same Sharpe ({sharpe(good):.2f})\nbut very different tail")
ax1.set_xlabel("daily return"); ax1.legend(fontsize=9); ax1.set_xlim(-0.1,0.1)

ths=np.linspace(1,250,60)
ax2.plot(ths,[CE(good,t) for t in ths],color="#16a34a",lw=2.5,label="CE Healthy")
ax2.plot(ths,[CE(bad,t)  for t in ths],color="#dc2626",lw=2.5,label="CE Crash-prone")
ax2.axhline(good.mean(),color="#888",ls=":",lw=1.5,label="mean (theta to 0)")
ax2.set_title("Entropic CE penalizes bad tails\nas theta (risk aversion) increases")
ax2.set_xlabel("theta  (risk aversion)"); ax2.set_ylabel("Certainty Equivalent")
ax2.legend(fontsize=9); ax2.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("motivating.png",dpi=130)
print("\n[plot] motivating.png saved")
