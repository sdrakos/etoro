# Honest Scope Admission

When a theoretical result or numerical experiment doesn't cover everything you'd hoped, say so explicitly. Reviewers respect this; they punish overclaiming. This file captures the patterns that worked in Paper 2.

## Core principle

If you find yourself mentally reframing a claim to sound stronger than the evidence allows, you're about to make a reviewer-bait mistake. The reframing instinct is a signal to STOP and admit the limitation explicitly.

## The three moves

### Move 1: Name what the theorem does NOT prove

After the theorem and its proof, add a remark listing what's not covered. Example from Paper 2:

```latex
\begin{remark}[Scope of Theorem~\ref{thm:bangbang}]
Theorem~\ref{thm:bangbang} establishes single-epoch greedy invariance 
across FOSD-monotone rewards. It does not claim:
\begin{enumerate}
\item Global optimality over multi-epoch horizons with budget constraints;
\item Invariance for non-FOSD-monotone rewards (e.g., pure variance penalties);
\item That continuous-action optima coincide (Method B demonstrates they do not).
\end{enumerate}
\end{remark}
```

The reviewer sees you've already thought about these boundary cases. They're disarmed.

### Move 2: Separate what's proven from what's observed

When empirical observations exceed what's formally proven, distinguish them explicitly. Paper 2's Lagrangian A.7.3 does this:

```
What Theorem~\ref{thm:lagrangian} DOES establish:
- Pointwise-λ invariance at any single decision epoch.

What is empirically observed but NOT formally proven:
- Mean and CVaR rewards produce identical global SLSQP optima.

The gap between the two: the theorem covers single-epoch greedy; 
the empirical observation is about global multi-epoch SLSQP. 
Closing this gap requires a time-varying λ_k dynamic programming 
extension, deferred to future work.
```

The paper neither claims the empirical observation as a theorem nor dismisses it as irrelevant. It names the gap honestly.

### Move 3: Name the future work explicitly

End limitation sections with concrete future directions. "Future work" sections that are vague ("we hope to extend...") read as hand-waving. Specific ones read as research programme:

```latex
\subsection{Open items for the final version}

The following items remain for the final manuscript:

\begin{enumerate}
\item An explicit characterisation of the conditions under which a 
density is "reachable" by admissible therapies on $[0, t_k]$, to 
make the theorem's quantifier precise. 

\item Extension to continuous-action greedy policies, which would 
require a calculus-of-variations version of the FOSD-monotonicity 
argument in Lemma~\ref{lem:fpe-monotone}.

\item A comparison to the Maier et al.\ (2021) posterior-in-state 
result along the following axis: our theorem fixes the reward and 
varies its form; Maier et al.\ fix the reward and vary the policy 
input. A unified treatment would clarify when density-awareness helps.
\end{enumerate}
```

Each item is specific enough that a reader could actually start working on it.

## When to hide vs admit

Sometimes a limitation is truly minor and doesn't need paper-level admission (e.g. "FEM convergence was only tested at resolution 200, not 400"). Other times a limitation is central and MUST be admitted.

Rule of thumb: if a reasonable reviewer would call it out as a major concern, admit it first. If it's a minor technical detail only relevant to expert readers, a brief footnote or no mention is fine.

Examples of MAJOR concerns that must be admitted:
- Numerical experiments only validate a subset of the theoretical claim
- The action menu is discrete but the underlying problem allows continuous actions
- The budget constraint is assumed tight in the theorem but can be slack in practice
- Parameter sensitivity was only tested on 30 patients, not a full population

Examples of MINOR concerns that can be skipped or footnoted:
- Convergence rate was verified at one mesh size
- The specific random seed used was 2025 (mention in reproducibility section, not a concern)
- The choice of SLSQP over trust-constr was based on convenience (noted in methods)

## Example: the Lagrangian scope discovery

Paper 2 original draft for §A.7.3 claimed "Theorem 8 explains why mean and CVaR schedules coincide at B=0.32 budget". Numerical Part 2 verification revealed this claim was WRONG — fixed-λ greedy is binary (all-high or all-low), not structured bang-bang. The SLSQP structured schedules come from global optimization with explicit equality constraint, not from Lagrangian dynamics.

The wrong response would have been to edit the theorem to claim something broader (false confidence).

The right response, which was taken:

1. Added explicit paragraph naming the gap:
   > "What Theorem 8 does NOT recover: a single-λ greedy policy on the discrete action menu tends to produce uniformly bang-bang schedules — all c^(L) until λ exceeds some threshold, then all zero — because a fixed per-epoch penalty cannot trade off current-epoch utility against future-epoch utility."

2. Narrowed the theorem's scope to single-epoch greedy pointwise-λ invariance (provable, verified 330/330).

3. Flagged the time-varying-λ extension as future work:
   > "Full equivalence between global SLSQP schedules and multi-step Lagrangian dynamic programming requires a time-varying multiplier λ_k and is beyond the scope of this appendix."

4. Made the numerical verification report match the theorem scope (only Part 1 pointwise invariance verified, Part 2 deferred).

The result: a weaker but correct theorem with a clean scope admission. Reviewer-defensible. Extensible in follow-up work.

## Language patterns that signal admission

These phrasings read as honest rather than apologetic:

- "Theorem X does not claim..." (direct, confident)
- "The following items remain..." (programmatic, forward-looking)
- "This result applies in the discrete-action regime; the continuous case is..." (specific boundary)
- "We have verified this numerically for [specific setup]; more general conditions..." (scoped claim)
- "The proof requires [hypothesis]. Relaxing this would need..." (technical caveat)

Phrasings to AVOID (signal defensiveness or overclaiming):

- "Of course, this is only a first step..." (defensive)
- "While limited, this result suggests..." (hedging)
- "Obviously, more work is needed..." (vague)
- "It is well-known that..." (citation-free appeal to authority)
- "We believe..." (subjective without evidence)

## Length calibration

Scope admissions should be roughly 1/10 of the theorem section length:
- 1-page theorem → 2-3 sentence scope remark
- 3-page theorem → 1-paragraph scope remark
- 5+ page theorem → full subsection with enumerated limitations and future work

Don't over-apologize. Once the limitation is named, move on. A single paragraph that names three specific limitations is more effective than a page of hand-wringing.

## The positive framing

Every limitation is also an opportunity for future work. Frame them that way:

- "This theorem covers single-epoch; the multi-epoch extension via dynamic programming is a natural next step."
- "The discrete-action assumption is essential here; relaxing it opens a connection to calculus of variations."
- "The FOSD-monotone class covers all our target rewards but excludes pure-variance penalties; characterising the appropriate ordering for those is an open problem."

Each of these (a) admits the limitation, (b) points toward a concrete research direction, (c) positions the current result as a building block rather than a final answer. This is how serious work gets structured.
