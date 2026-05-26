# Theorem and Proof Structure

The structure proven in Paper 2's Appendix A (Bang-bang invariance theorem) and Appendix B (Pointwise Lagrangian invariance theorem). Use this for any new theorem with non-trivial proof.

## Six-part structure

Every formal theorem section should contain:

1. **Status paragraph** (italics, at top) — honest summary of what the proof covers and what it defers
2. **Preliminary definitions** — set up notation explicitly
3. **Core lemmas** — self-contained, each with proof
4. **Main theorem** — formal statement
5. **Proof** — combining the lemmas
6. **Scope remark** — what the theorem does NOT cover

Together these are typically 3-6 pages. Anything shorter probably skips something; anything longer probably overexplains.

## Part 1: Status paragraph

Before the first mathematical content of the appendix, put an italics paragraph that summarises the proof architecture honestly. Example from Paper 2 Appendix A:

> *Status of this appendix: the proof below consists of three components: (i) a closed-form derivation of the FPE transition kernel (Lemma 2), which is elementary once the spatial homogeneity of the transformed FPE is recognised; (ii) a pathwise coupling argument establishing FOSD-monotonicity of the forward propagation in the therapy level (Lemma 3), which is self-contained; and (iii) the main theorem proper, which follows by pairwise application of the lemmas and is mechanical. A numerical cross-check on the FEM solver (Remark 6) confirms that the discretised dynamics preserve the FOSD ordering inherited from the analytical kernel. Remark 4 cites Karlin and Rubin (1956) for the more general MLR-based framing that our spatial-homogeneity-based coupling argument shortcuts.*

What makes this paragraph good: it flags what's elementary, what's the core work, and what's deferred to other literature. A reviewer reading this knows in 30 seconds whether they need to scrutinise the proof line-by-line or can skim.

## Part 2: Preliminary definitions

Introduce every non-standard symbol explicitly. Don't assume the reader remembers from the main body. Example:

```latex
\subsection{Preliminary definitions and notation}

Let $\mathcal{P}(\mathbb{R}_{\ge 0})$ denote the set of probability 
density functions on $\mathbb{R}_{\ge 0}$ with finite first two moments. 
For $P, Q \in \mathcal{P}(\mathbb{R}_{\ge 0})$ with cumulative 
distribution functions $F_P, F_Q$, we say $P$ dominates $Q$ in 
first-order stochastic dominance, written $P \succeq_{\mathrm{FOSD}} Q$, if
\begin{equation}
F_P(y) \le F_Q(y) \quad \text{for all } y \in \mathbb{R}_{\ge 0}.
\end{equation}
```

Two rules:
- Every `\mathcal{}`, `\Phi`, `\succeq_{\mathrm{FOSD}}` symbol must be defined before use
- Every definition that generalises a standard notion should cite a source (Karlin-Rubin for MLR, standard probability texts for FOSD)

## Part 3: Core lemmas

Each lemma should be:
- **Self-contained:** reader can verify it without reading the main theorem
- **Numerically checkable:** if you can't write a 20-line Python script that tests the lemma on Paper 1 parameters, the lemma is probably too abstract
- **Named descriptively:** "Closed-form transition kernel" not "Lemma 2"

Typical lemma pattern:

```latex
\begin{lemma}[Descriptive name]
\label{lem:name}
Let [hypothesis 1]. Let [hypothesis 2]. Then [conclusion].
\end{lemma}

\begin{proof}
[Direct argument. 3-8 lines typical. If longer than 15 lines, 
probably needs to be split into sub-lemmas.]
\qedhere
\end{proof}

\begin{remark}[Optional]
Observational comment about the lemma, e.g. "Note that $M_k(c)$ is 
strictly decreasing in $c$: higher doses produce smaller conditional 
means." This kind of inline observation helps the reader and 
sometimes saves restating in the main proof.
\end{remark}
```

## Part 4: Main theorem statement

The theorem statement should be narrow — claim exactly what's provable, no more. Example of narrow scope from Paper 2:

```latex
\begin{theorem}[Bang-bang invariance]
\label{thm:bangbang}
Let $r_1, r_2$ be two FOSD-monotone reward functionals on 
$\mathcal{P}(\mathbb{R}_{\ge 0})$. For every reachable density 
$P_k$ at epoch $k$, the greedy one-step policy under $r_1$ 
coincides with the greedy one-step policy under $r_2$:
\begin{equation}
\arg\min_{a \in \mathcal{A}} r_1(\Phi^a_k[P_k]) 
\;=\; \arg\min_{a \in \mathcal{A}} r_2(\Phi^a_k[P_k]).
\end{equation}
\end{theorem}
```

Three features of this statement:
- **Narrow domain:** "FOSD-monotone" excludes `-Var[Y]` and similar — honest about scope
- **Narrow action:** "one-step greedy" not "globally optimal" — doesn't overclaim
- **Explicit hypothesis:** "reachable density" — flagged as requiring further definition

## Part 5: Proof

The proof combines the lemmas. Keep it mechanical once the lemmas are in place — if the proof gets creative, the creativity should live in a lemma.

```latex
\begin{proof}
Fix $P_k$ reachable and consider two adjacent actions $c^{(\ell)}, c^{(\ell+1)} \in \mathcal{A}$ with $c^{(\ell)} < c^{(\ell+1)}$. By Lemma~\ref{lem:fpe-monotone},
\begin{equation}
\Phi^{c^{(\ell)}}_k[P_k] \succeq_{\mathrm{FOSD}} \Phi^{c^{(\ell+1)}}_k[P_k].
\end{equation}
By FOSD-monotonicity of both $r_1$ and $r_2$ (Definition~\ref{def:fosd-monotone}),
\begin{equation}
r_i(\Phi^{c^{(\ell)}}_k[P_k]) \ge r_i(\Phi^{c^{(\ell+1)}}_k[P_k]), \quad i = 1, 2.
\end{equation}
Therefore the sign of $r_i(\Phi^{c^{(\ell)}}_k) - r_i(\Phi^{c^{(\ell+1)}}_k)$ is non-negative for both $i=1,2$, and in particular the $\arg\min$ over $\mathcal{A}$ coincides.
\end{proof}
```

## Part 6: Scope remark

This is the part most papers skip and it's the part reviewers love. Name explicitly what the theorem does NOT cover:

```latex
\begin{remark}[Scope of the theorem]
\label{rem:scope}
Theorem~\ref{thm:bangbang} does not claim:
\begin{enumerate}
\item that the greedy policy is globally optimal (it is not, in general, for non-zero discount rates or budget constraints);
\item that the result extends to non-FOSD-monotone rewards such as pure variance penalties $-\operatorname{Var}[Y]$, which can distinguish actions invisible to FOSD-ranked rewards;
\item that the discrete action assumption is essential (continuous-action optimisation in \S\ref{sec:methodB} yields genuinely different schedules at different $\lambda$).
\end{enumerate}
The practical consequence is that the theorem explains why our CVaR-based and mean-based single-epoch policies agree, not why our global SLSQP optima agree.
\end{remark}
```

Why this works: a hostile reviewer looking for overclaims won't find any, because they're pre-empted here. The theorem's usefulness is preserved ("explains why our single-epoch policies agree") while overreach is blocked.

## Common failure modes

Caught in Paper 2 self-review:

1. **Redundant hypothesis.** The original theorem statement had "and the propagated densities are totally ordered under FOSD" — but this is automatic from Lemma 3, not an additional assumption. Whenever a hypothesis might be implied by another, check. Drop redundant ones.

2. **Sign direction wrong.** The original §3.2 had `Φ^a[P] ⪰ Φ^b[P]` meaning "higher dose gives larger density" — the opposite of the truth. Whenever a direction is asserted, cross-check against a concrete example (higher dose → smaller tumor → density mass shifts left → dominated density, not dominating).

3. **Proof claims more than statement.** If the proof establishes something stronger than the statement, either strengthen the statement or weaken the proof text. Don't leave a mismatch — it looks like sloppy reasoning.

4. **Claim extends beyond numerics.** The original Lagrangian A.7.3 claimed "structured bang-bang pattern" but numerics showed fixed-λ greedy is binary (all-high or all-low). Rewrite the claim to match what's actually provable.

## Numerical cross-check remark

For proofs that have numerical companions, add a remark at the end:

```latex
\begin{remark}[Numerical verification]
\label{rem:numerical-verification}
Theorem~\ref{thm:bangbang} was verified numerically on 30 
patients (sampled with $a \in [0.04, 0.14]$, $b \in [0.02, 0.09]$, 
$\sigma \in [0.01, 0.04]$, seed 2025). For each patient and each 
pair of FOSD-monotone rewards $(r_1, r_2) \in \{E[Y], \mathrm{CVaR}_{0.9}[Y]\}$, 
the greedy $\arg\min$ over the 11-level action menu 
$\mathcal{A} = \{0, 0.008, \ldots, 0.08\}$ agreed exactly at 
the initial density $P_0$: all $30 \times 11 = 330$ pairs match. 
Verification script: \url{https://github.com/sdrakos/gompertz-fpe-therapy/blob/main/scripts/verify_theorem.py}
\end{remark}
```

This remark serves two purposes: (a) closes the gap between proof and practice for readers who don't trust FEM discretisations, (b) gives reviewers a path to independent verification.
