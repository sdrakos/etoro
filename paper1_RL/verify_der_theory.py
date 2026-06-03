"""
verify_der_theory.py  -- Αριθμητικη επαληθευση ΚΑΘΕ θεωρητικου ισχυρισμου του paper
================================================================================
 Καθε claim ελεγχεται με ΔΥΟ ανεξαρτητους τροπους (exact entropic formula vs
 ανεξαρτητη κατασκευη), και κανει assert. Seed 2025. Τρεχει σε <60s.

 Claims:
  C1. CE_θ -> μ  καθως θ->0           (risk-neutral limit)
  C2. CE_θ ≈ μ - (θ/2)σ²  (1ης ταξης) (mean-variance)
  C3. Cumulant expansion:
        CE_θ = κ1 - (θ/2)κ2 + (θ²/6)κ3 - (θ³/24)κ4 + O(θ⁴)
  C4. DER telescoping:  Σ_t DER_t = CE_T - CE_0   (EMA recursion)
  C5. Asymmetry:  ισο μεγεθος ζημιας τιμωραιται περισσοτερο απο κερδος (θ>0)
  C6. Motivating example: ιδιο μ,σ (ιδιο Sharpe) αλλα αντιθετο skew -> CE διαφερει
"""
import numpy as np
from scipy import stats
SEED = 2025
rng = np.random.default_rng(SEED)

def CE(R, theta):
    """Exact entropic certainty equivalent, log-sum-exp stable."""
    m = np.max(-theta*R)
    return -(1.0/theta)*(m + np.log(np.mean(np.exp(-theta*R - m))))

def cumulants(R):
    mu = R.mean(); s2 = R.var()
    k3 = np.mean((R-mu)**3); k4 = np.mean((R-mu)**4) - 3*s2**2   # excess (4th cumulant)
    return mu, s2, k3, k4

PASS = []
def check(name, cond, detail=""):
    PASS.append(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}   {detail}")

print("="*70); print("ΕΠΑΛΗΘΕΥΣΗ ΘΕΩΡΙΑΣ DER  (seed=2025)"); print("="*70)

# sample με γνωστες ροπες (mixture -> ελεγχομενο skew/kurtosis)
R = 0.0008 + 0.012*rng.standard_normal(2_000_000)
R += np.where(rng.random(2_000_000)<0.02, -0.05, 0.0)        # αρνητικα jumps -> -skew
mu, s2, k3, k4 = cumulants(R); sig=np.sqrt(s2)
print(f"\nδειγμα: μ={mu:.5f}, σ={sig:.5f}, skew={k3/sig**3:.3f}, exkurt={k4/s2**2:.3f}\n")

# --- C1: θ->0 limit ---
ce_small = CE(R, 1e-4)
check("C1 risk-neutral limit (θ→0 ⇒ CE→μ)", abs(ce_small-mu)<1e-5,
      f"CE(θ=1e-4)={ce_small:.6f} vs μ={mu:.6f}")

# --- C2: first-order mean-variance ---
th=2.0
ce2_exact = CE(R, th); ce2_approx = mu - 0.5*th*s2
check("C2 1st-order ≈ μ-(θ/2)σ²", abs(ce2_exact-ce2_approx)<5e-4,
      f"exact={ce2_exact:.6f} vs μ-(θ/2)σ²={ce2_approx:.6f}")

# --- C3: cumulant expansion (4 ορων) ---
def CE_series(theta):
    return mu - (theta/2)*s2 + (theta**2/6)*k3 - (theta**3/24)*k4
errs=[]
for th in [1,2,4,8]:
    e=abs(CE(R,th)-CE_series(th)); errs.append(e)
    print(f"     θ={th}:  CE_exact={CE(R,th):.6f}  CE_series4={CE_series(th):.6f}  err={e:.2e}")
check("C3 cumulant expansion (4 ορων) ακριβης για μικρα θ", errs[1]<1e-4,
      f"err(θ=2)={errs[1]:.2e}")

# --- C4: DER telescoping ---
def DER_stream(R, theta, eta=0.05):
    M0 = np.exp(-theta*R[0]); M=M0; ders=[]
    for t in range(1,len(R)):
        Mn=(1-eta)*M+eta*np.exp(-theta*R[t])
        ders.append(-(1/theta)*np.log(Mn/M)); M=Mn
    CE_T = -(1/theta)*np.log(M); CE_0 = -(1/theta)*np.log(M0)
    return np.sum(ders), CE_T-CE_0
Rseq = R[:5000]
s_der, ce_diff = DER_stream(Rseq, theta=50.0)
check("C4 DER telescoping (Σ DERₜ = CE_T - CE_0)", abs(s_der-ce_diff)<1e-9,
      f"ΣDER={s_der:.6f}  CE_T-CE_0={ce_diff:.6f}")

# --- C5: asymmetry / risk-aversion: δικαιο στοιχημα ±g (μεσος 0) εχει CE<0,
#         και ολο πιο αρνητικο οσο μεγαλωνει το θ (η ζημια βαραινει περισσοτερο) ---
g=0.05; gamble=np.array([+g,-g])           # 50/50, μεσος = 0
ce50,ce100,ce200 = CE(gamble,50), CE(gamble,100), CE(gamble,200)
check("C5a δικαιο στοιχημα (μεσος 0) εχει CE<0 (θ=100)", ce100<0,
      f"CE(±{g}, θ=100)={ce100:.5f} < 0 = μεσος")
check("C5b μεγαλυτερο θ ⇒ πιο αρνητικο CE", ce200<ce100<ce50<0,
      f"CE(θ=50)={ce50:.4f} > CE(θ=100)={ce100:.4f} > CE(θ=200)={ce200:.4f}")

# --- C6: motivating example (ιδιο μ,σ, αντιθετο skew) ---
def match(x,m,s): return (x-x.mean())/x.std()*s+m
calm=0.0008+0.006*rng.standard_normal(200000)
bad = match(calm + np.where(rng.random(200000)<0.03,-0.05,0.0), 0.0008, 0.012)
good= match(calm + np.where(rng.random(200000)<0.03,+0.05,0.0), 0.0008, 0.012)
sh=lambda x:x.mean()/x.std()
check("C6a ιδιο Sharpe (good vs bad)", abs(sh(good)-sh(bad))<1e-6,
      f"Sh_good={sh(good):.4f}  Sh_bad={sh(bad):.4f}")
check("C6b CE διακρινει (CE_good > CE_bad, θ=100)", CE(good,100)>CE(bad,100),
      f"CE_good={CE(good,100):.5f} > CE_bad={CE(bad,100):.5f}")

print("\n"+"="*70)
print(f"ΣΥΝΟΛΟ: {sum(PASS)}/{len(PASS)} PASS")
assert all(PASS), "ΚΑΠΟΙΟΣ ΙΣΧΥΡΙΣΜΟΣ ΑΠΕΤΥΧΕ"
print("ΟΛΟΙ ΟΙ ΘΕΩΡΗΤΙΚΟΙ ΙΣΧΥΡΙΣΜΟΙ ΕΠΑΛΗΘΕΥΤΗΚΑΝ.")
print("="*70)
