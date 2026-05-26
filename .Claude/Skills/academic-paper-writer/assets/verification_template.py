"""
Template for numerical verification of a paper claim.

Usage:
  1. Copy this file to /tmp/verify_<claim_name>.py
  2. Fill in the claim description in the docstring below
  3. Fill in the two-way computation (FEM + MC or analytical + numerical)
  4. Run: python /tmp/verify_<claim_name>.py
  5. Script should PASS (assert at end) or FAIL loudly with diagnostic output

Conventions:
  - Paper 1 parameters as defaults (a=0.1, b=0.05, σ=0.02, y0=5.0, T=8.0)
  - Seed 2025 for reproducibility
  - Scripts should run in <60 seconds
"""

import numpy as np
import sys

# Access gompertz-fpe-therapy package
sys.path.insert(0, '/home/claude/gompertz-fpe-therapy/src')
from gompertz_fpe import FPE, domain_for_T
from gompertz_fpe.density import mean, cdf

# --------------------------------------------------------------
# Paper 1 / Paper 2 standard parameters
# --------------------------------------------------------------

a_true = 0.1
b_true = 0.05
sigma_true = 0.02
y0 = 5.0
T = 8.0
n_epochs = 8
dt_epoch = T / n_epochs  # = 1.0
C_max = 0.08
B = 0.32
delta = 1.15
epsilon = 0.05
SEED = 2025


def solve_setup(a=a_true, b=b_true, sig=sigma_true):
    """Initialise FEM solver and initial density for given parameters."""
    xmin, xmax = domain_for_T(a, b, sig, 0.0, T, y0)
    solver = FPE(a=a, b=b, sigma=sig, ne=200, xmin=xmin, xmax=xmax, dt=0.05)
    P0 = solver.initial_condition(y0=y0, width=0.3)
    return solver, P0


def cvar_90(P, nodes):
    """CVaR at 90% = E[Y | Y >= VaR_0.9]"""
    F = cdf(P, nodes)
    idx = np.searchsorted(F, 0.9)
    if idx >= len(nodes):
        idx = len(nodes) - 1
    var = nodes[idx]
    mask = nodes >= var
    if not mask.any():
        return mean(P, nodes)
    num = np.trapezoid(nodes[mask] * P[mask], nodes[mask])
    denom = np.trapezoid(P[mask], nodes[mask]) + 1e-12
    return num / denom


# --------------------------------------------------------------
# TEMPLATE: fill in the claim to verify
# --------------------------------------------------------------

def verify_claim():
    """
    Claim: [TODO: one-sentence description of what we're verifying].

    Method: compute [quantity] two ways:
      (a) via FEM solver [or analytical formula]
      (b) via Monte Carlo [or alternative computation]

    Expected: agreement within tolerance [TODO: specify tolerance].
    """

    solver, P0 = solve_setup()

    # Way 1: FEM computation
    PT_fem = solver.solve_from_state(P0, 0.0, T, lambda t: 0.0)
    quantity_fem = mean(PT_fem, solver.nodes)  # Example: terminal mean

    # Way 2: Monte Carlo (fill in appropriate SDE integration)
    n_samples = 10000
    rng = np.random.default_rng(SEED)
    dt_mc = 0.01
    n_steps = int(T / dt_mc)

    # Transform y -> Y = ln(y) / σ
    Y = np.full(n_samples, np.log(y0) / sigma_true)
    for k in range(n_steps):
        t = k * dt_mc
        # CRITICAL: drift sign is +μ, not -μ (see numerical-verification.md)
        mu = np.exp(b_true * t) / sigma_true * (a_true - 0.0 - sigma_true**2 / 2)
        D = np.exp(2 * b_true * t)
        Y = Y + mu * dt_mc + np.sqrt(D * dt_mc) * rng.standard_normal(n_samples)

    y_final = np.exp(sigma_true * Y)
    quantity_mc = y_final.mean()

    # Compare
    error = abs(quantity_fem - quantity_mc)
    print(f"FEM:         {quantity_fem:.4f}")
    print(f"Monte Carlo: {quantity_mc:.4f}")
    print(f"Error:       {error:.4f}")

    tolerance = 0.1  # TODO: adjust based on expected MC precision
    assert error < tolerance, f"FEM and MC disagree by {error:.4f} (> {tolerance})"
    print(f"\n✓ Claim verified within tolerance {tolerance}")


# --------------------------------------------------------------
# Additional verification patterns (uncomment as needed)
# --------------------------------------------------------------

def verify_fosd_ordering(action_low=0.0, action_high=C_max):
    """Check F_low(y) - F_high(y) sign over the grid."""
    solver, P0 = solve_setup()
    P_low = solver.solve_from_state(P0, 0.0, T, lambda t: action_low)
    P_high = solver.solve_from_state(P0, 0.0, T, lambda t: action_high)
    F_low = cdf(P_low, solver.nodes)
    F_high = cdf(P_high, solver.nodes)

    # Higher dose should produce FOSD-dominated density:
    # F_high(y) >= F_low(y), i.e., F_low - F_high <= 0
    violations = F_low - F_high
    print(f"FOSD check:")
    print(f"  max(F_low - F_high) = {violations.max():.6f}  (should be <= 0)")
    print(f"  min(F_low - F_high) = {violations.min():.6f}")

    tol = 1e-5
    assert violations.max() <= tol, f"FOSD violated: {violations.max():.6f}"
    print(f"\n✓ FOSD ordering holds within tolerance {tol}")


def verify_invariance(n_patients=30, n_lambdas=11):
    """
    Check that two FOSD-monotone rewards agree on greedy argmin
    across patients and lambda values.
    """
    rng = np.random.default_rng(SEED)
    patients = [(rng.uniform(0.04, 0.14),
                 rng.uniform(0.02, 0.09),
                 rng.uniform(0.01, 0.04)) for _ in range(n_patients)]

    action_menu = np.linspace(0.0, C_max, 11)
    lambda_grid = np.linspace(0.0, 1.0, n_lambdas)

    def greedy_argmin(P_init, solver, lam, reward_fn):
        best_g, best_a = np.inf, 0.0
        for a in action_menu:
            P_next = solver.solve_from_state(P_init, 0.0, dt_epoch, lambda t: a)
            g = reward_fn(P_next, solver.nodes) + lam * a * dt_epoch
            if g < best_g:
                best_g, best_a = g, a
        return best_a

    n_pairs = 0
    n_agreements = 0
    for a, b, sig in patients:
        solver, P0 = solve_setup(a, b, sig)
        for lam in lambda_grid:
            a_mean = greedy_argmin(P0, solver, lam, mean)
            a_cvar = greedy_argmin(P0, solver, lam, cvar_90)
            n_pairs += 1
            if abs(a_mean - a_cvar) < 1e-10:
                n_agreements += 1

    print(f"\nInvariance check: {n_agreements}/{n_pairs} pairs agree")
    print(f"({100 * n_agreements / n_pairs:.1f}%)")
    assert n_agreements == n_pairs, f"Disagreements: {n_pairs - n_agreements}"
    print("✓ Invariance holds across all pairs")


# --------------------------------------------------------------
# Entry point
# --------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("Numerical verification")
    print("=" * 70)

    verify_claim()
    # verify_fosd_ordering()
    # verify_invariance()

    print("\n" + "=" * 70)
    print("All checks passed")
    print("=" * 70)
