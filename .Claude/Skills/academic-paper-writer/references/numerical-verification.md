# Numerical Verification

The Monte Carlo cross-check that caught the Paper 2 SDE sign error. Any time a proof asserts a numerical claim (monotonicity, ordering, convergence), run this check before writing the proof.

## Core principle

Compute the same quantity two different ways and require agreement. If they disagree, the analytical claim is wrong (not the numerics, almost never).

Typical pairings:
- FEM solver output vs direct Monte Carlo SDE simulation
- Closed-form Gaussian kernel vs FEM propagation
- Analytical moment vs numerical density integration
- Expected proof conclusion (e.g. FOSD ordering) vs computed CDFs

## Standard parameters

Always use Paper 1's true parameters as the default test case:

```python
# Paper 1 ground truth
a_true = 0.1
b_true = 0.05
sigma_true = 0.02
y0 = 5.0
T = 8.0

# Optimization setup from Paper 2
n_epochs = 8
dt_epoch = T / n_epochs  # = 1.0
C_max = 0.08
B = 0.32  # budget
delta = 1.15  # corridor upper bound factor
epsilon = 0.05  # chance constraint slack

# Reproducibility
seed = 2025
```

For patient stratification tests (30-patient cohort), use these ranges with `np.random.default_rng(2025)`:

```python
a_range = (0.04, 0.14)
b_range = (0.02, 0.09)
sigma_range = (0.01, 0.04)
```

## SDE sign convention (CRITICAL)

The transformed Gompertz FPE corresponds to the SDE:

```
dY(t) = +μ(t; C(t)) dt + √D(t) dW(t)
```

with drift `μ(t; c) = e^{bt}/σ · (a - c - σ²/2)` and diffusion `D(t) = e^{2bt}`.

**This is `+μ`, not `-μ`.** The wrong sign causes E[Y(T)] to diverge from FEM by ~6 units (for Paper 1 parameters), easy to catch with Monte Carlo. If a proof draft writes `-μ`, STOP and re-verify before proceeding.

Verification script template:

```python
import numpy as np

def verify_sign_convention(n_samples=10000):
    """
    Compare FEM expectation against Monte Carlo with +μ vs -μ.
    Expected: +μ agrees with FEM within ~0.02; -μ diverges by ~6.
    """
    # FEM reference (from gompertz-fpe-therapy)
    import sys
    sys.path.insert(0, '/home/claude/gompertz-fpe-therapy/src')
    from gompertz_fpe import FPE, domain_for_T
    from gompertz_fpe.density import mean
    
    xmin, xmax = domain_for_T(a_true, b_true, sigma_true, 0.0, T, y0)
    solver = FPE(a=a_true, b=b_true, sigma=sigma_true, 
                 ne=200, xmin=xmin, xmax=xmax, dt=0.05)
    P0 = solver.initial_condition(y0=y0, width=0.3)
    PT = solver.solve_from_state(P0, 0.0, T, lambda t: 0.0)  # no therapy
    fem_mean = mean(PT, solver.nodes)
    
    # Monte Carlo with +μ (correct)
    rng = np.random.default_rng(seed)
    dt_mc = 0.01
    n_steps = int(T / dt_mc)
    Y = np.full(n_samples, np.log(y0) / sigma_true)  # Y = ln(y)/σ, transformed
    for k in range(n_steps):
        t = k * dt_mc
        mu = np.exp(b_true * t) / sigma_true * (a_true - 0.0 - sigma_true**2 / 2)
        D = np.exp(2 * b_true * t)
        Y = Y + mu * dt_mc + np.sqrt(D * dt_mc) * rng.standard_normal(n_samples)
    y_final = np.exp(sigma_true * Y)
    mc_plus_mean = y_final.mean()
    
    # Monte Carlo with -μ (wrong)
    rng = np.random.default_rng(seed)
    Y = np.full(n_samples, np.log(y0) / sigma_true)
    for k in range(n_steps):
        t = k * dt_mc
        mu = np.exp(b_true * t) / sigma_true * (a_true - 0.0 - sigma_true**2 / 2)
        D = np.exp(2 * b_true * t)
        Y = Y - mu * dt_mc + np.sqrt(D * dt_mc) * rng.standard_normal(n_samples)
    y_final = np.exp(sigma_true * Y)
    mc_minus_mean = y_final.mean()
    
    print(f"FEM E[Y(T)]        = {fem_mean:.4f}")
    print(f"MC with +μ E[Y(T)] = {mc_plus_mean:.4f}  (err {abs(fem_mean - mc_plus_mean):.4f})")
    print(f"MC with -μ E[Y(T)] = {mc_minus_mean:.4f}  (err {abs(fem_mean - mc_minus_mean):.4f})")
    
    assert abs(fem_mean - mc_plus_mean) < 0.1, "FEM and +μ MC disagree"
    assert abs(fem_mean - mc_minus_mean) > 1.0, "Sign test non-diagnostic"
    print("\n✓ Sign convention verified: use +μ")

if __name__ == "__main__":
    verify_sign_convention()
```

## FOSD ordering verification

For theorems claiming FOSD ordering of propagated densities:

```python
def verify_fosd_ordering(action_low, action_high, params=None):
    """
    Check that higher dose produces FOSD-dominated density.
    Returns: max(F_high - F_low) over the grid. Should be <= tiny_tol.
    """
    from gompertz_fpe.density import cdf
    # ... setup solver, propagate both
    P_low = solver.solve_from_state(P0, 0.0, T, lambda t: action_low)
    P_high = solver.solve_from_state(P0, 0.0, T, lambda t: action_high)
    
    F_low = cdf(P_low, solver.nodes)
    F_high = cdf(P_high, solver.nodes)
    
    # Higher dose → smaller Y → F_high(y) ≥ F_low(y) for all y
    # (F_high dominates F_low in CDF order = low dominates high in FOSD sense)
    violations = F_low - F_high  # should be <= 0 everywhere
    return violations.max(), violations.min()
```

Edge cases to test (from Paper 2):
- Tiny dose difference: `action_low=0.040, action_high=0.041`
- Max dose difference: `action_low=0.0, action_high=C_max`
- Multiple time horizons: `T=1, 2, 4, 8`

All should satisfy `violations.max() <= 1e-5` (numerical tolerance of FEM).

## Theorem-invariance verification

For claims that two rewards produce the same greedy choice:

```python
def verify_invariance(reward_A, reward_B, n_patients=30, n_lambdas=11):
    """
    Count agreement pairs across (patient, lambda) grid.
    Target: 100% agreement for FOSD-monotone rewards.
    """
    rng = np.random.default_rng(2025)
    patients = [(rng.uniform(0.04, 0.14), 
                 rng.uniform(0.02, 0.09), 
                 rng.uniform(0.01, 0.04)) for _ in range(n_patients)]
    
    action_menu = np.linspace(0.0, C_max, 11)
    lambda_grid = np.linspace(0.0, 1.0, n_lambdas)
    
    n_pairs = 0
    n_agreements = 0
    disagreements = []
    
    for patient_idx, (a, b, sig) in enumerate(patients):
        solver, P0 = solve_setup(a, b, sig)
        for lam in lambda_grid:
            a_A = greedy_argmin(P0, solver, lam, reward_A, action_menu)
            a_B = greedy_argmin(P0, solver, lam, reward_B, action_menu)
            n_pairs += 1
            if abs(a_A - a_B) < 1e-10:
                n_agreements += 1
            else:
                disagreements.append((patient_idx, lam, a_A, a_B))
    
    print(f"{n_agreements}/{n_pairs} pairs agree ({n_agreements/n_pairs*100:.1f}%)")
    if disagreements:
        print("Disagreements:")
        for d in disagreements[:5]:
            print(f"  patient {d[0]}, λ={d[1]:.3f}: A={d[2]}, B={d[3]}")
    return n_agreements, n_pairs, disagreements
```

## When verification contradicts intuition

If numerics disagree with the intended claim, STOP and investigate. The Paper 2 Lagrangian Part 2 case: intuition said "fixed-λ greedy reproduces structured bang-bang" but numerics showed binary switching (all-high or all-low). The correct response was to:

1. Document the numerical finding explicitly
2. Rewrite the theorem statement to match what's provable
3. Add a scope remark acknowledging the limitation
4. Flag the gap as future work (time-varying `λ_k` dynamic programming)

**Never edit the numerics to match the intuition.** That's scientific misconduct. The numerics are the ground truth for testable claims.

## Script conventions

- Scripts go in `/tmp/verify_<claim>.py`
- Each script self-contained: imports, parameters, function definitions, `if __name__ == "__main__":` block
- Print human-readable output with expected vs observed values
- End with `assert` statements that will fail loudly if the claim is violated
- Scripts should run in <60 seconds (reduce `n_samples` or `n_steps` if slower)
