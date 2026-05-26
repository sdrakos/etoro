# Self-Review Checklist (Reviewer Mode)

After finishing any substantive section, run this checklist as a separate pass with the mindset "what would a hostile reviewer catch?" This pass is different from the writing pass — do it after taking a break if possible, or at minimum after finishing the section and moving mentally to something else before returning.

Two concrete discoveries in Paper 2 came from this pass: the SDE sign error (which would have been reviewer-caught in 5 minutes if published) and the Lagrangian scope overclaim (reviewer-caught within a day).

## Ten-item checklist

### 1. Sign conventions

Every equation involving drift, flux, or direction: cross-check against a concrete example.
- Does higher dose produce smaller tumor? Then `μ(c)` should be decreasing in `c` for the tumor-size variable.
- Does the SDE write `+μ dt` or `-μ dt`? Match the convention to the FPE form.
- Does the FOSD direction say "higher dose → dominated density" or "dominating"? Pick one and verify with Monte Carlo.

If any direction feels unfamiliar, STOP and write a 20-line verification script.

### 2. Undefined symbols

Every symbol in a formal statement must be defined before its first use. Skim the theorem/proof and list every mathematical symbol; for each, confirm there's a prior `\mathcal{}` or `\coloneqq` or "Let X denote..." introduction.

Common offenders: `\Phi^a_k`, `\mathcal{P}`, `\succeq_{\mathrm{FOSD}}`, `\mathcal{A}` — these need explicit definition.

### 3. Unstated hypotheses

Check every implication in the proof. If something is used that wasn't in the theorem's hypothesis, either add it to the hypothesis or derive it in a prior lemma. Don't let a proof use "continuity of the map `c → Φ^c[P]`" if continuity wasn't established.

### 4. Redundant hypotheses

The opposite problem: if a hypothesis is implied by another, drop it. The Paper 2 original theorem had "the propagated densities are totally ordered under FOSD" — but this is automatic from Lemma 3. The hypothesis was redundant.

### 5. Proof claims vs theorem statement

The proof should establish exactly what the theorem states — no less, no more. If the proof accidentally proves more, either strengthen the statement or weaken the proof text. A mismatch looks sloppy.

### 6. Numerical claims vs proofs

Every numerical claim ("330/330 pairs agree", "k_star = 4 for all patients", "error < 0.02") must be traceable to a script that was actually run. Don't cite numerical results from memory — re-run or reference the specific script path in `/tmp/verify_*.py`.

### 7. Scope of the result

Add a "Scope of the theorem" or "Limitations" remark that explicitly names what's NOT proven. Did you establish single-epoch greedy equivalence? Say so, and note that multi-epoch equivalence is not proven. Did you verify with discrete 11-level action menu? Say so, and note that continuous-action results may differ.

### 8. Citations match claims

Every named concept, technique, or prior result has a citation. Every citation's content actually supports the claim being made. If you cite "Maier et al. (2021)" for a specific claim, open the paper and confirm that claim is actually there.

### 9. Consistency of notation

Same concept, same symbol, throughout. If you use `y` for tumor size, don't switch to `x` in the next section. If you use `C_max` with underscore-subscript, don't write `C^{max}` with superscript elsewhere. This discipline is boring but important — inconsistency signals sloppiness to reviewers.

### 10. Tumor vs tumour spelling

Paper should pick one (British or American) and stick with it. Paper 2 uses "tumor" throughout. Search the TeX source for variants and normalise.

## Running the checklist

Read through the section once with each item in mind. Flag issues as you go. Batch-fix at the end rather than fix-as-you-find — the batch approach maintains the reviewer mindset.

Typical time: 15-30 minutes for a 3-4 page theorem section. Longer is a sign the section has structural problems, not just detail issues.

## Red flags that trigger extra scrutiny

- Any paragraph using the phrase "it is easy to see that" — expand or drop
- Any proof that ends with "the rest follows similarly" — reviewers hate this
- Any theorem whose proof takes more than one page — probably needs splitting
- Any use of "clearly" or "obviously" — if it's clear, prove it briefly; if it's not, don't claim it
- Any citation without page number for a specific claim (not a general reference)

## Reviewer-mode mindset

The reviewer doesn't know the author's intuition. The reviewer has limited patience and is looking for reasons to reject. Every ambiguity, every jump, every unstated assumption is a potential objection.

Write for this reviewer. Not to game them — to genuinely help them verify the result. Clarity that helps a hostile reviewer helps every reader.

## Honest self-report template

After running the checklist, produce a brief report (for Notion trail):

```
Self-review pass on §N.
Issues found:
1. [Category]: [specific issue]. Fix: [what was changed].
2. ...

Issues deferred (with reason):
1. [Category]: [issue]. Reason: [why not fixed now, e.g. needs further work].

Overall: [N%] ready for external review.
```

Example from Paper 2 Day 2:

```
Self-review pass on Appendix A.
Issues found:
1. Sign convention: Had -μ in Lemma 2; correct is +μ. Fixed 5 instances.
   Verified with MC: FEM=8.07, MC(+μ)=8.08 ✓, MC(-μ)=1.93 ✗.
2. Redundant hypothesis: "totally ordered" is automatic from Lemma 3. 
   Dropped from statement, noted in preliminary analysis.
3. Wrong FOSD direction in §3.2: had Φ^a ⪰ Φ^b (high-dose dominant); 
   correct is Φ^b ⪰ Φ^a. Flipped and added explanation.

Issues deferred:
1. Explicit reachability characterization (open research question, future work).

Overall: 85% → 90% ready for external review after these fixes.
```

This report goes in Notion as the paper trail.
