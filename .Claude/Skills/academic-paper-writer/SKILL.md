---
name: academic-paper-writer
description: Personal skill for Stefanos Drakos (AGEL AI, Rhodes) for writing, revising, and extending academic papers in applied mathematics, mathematical biology, stochastic control, and computational engineering — especially Fokker-Planck / FPE papers, stochastic tumor growth, Bayesian calibration, optimal therapy control, chance-constrained optimization, Pareto frontiers, and related theoretical or numerical work. Use this skill WHENEVER Stefanos mentions paper, manuscript, άρθρο, δημοσίευση, theorem, proof, απόδειξη, LaTeX, Zenodo, arXiv, preprint, FPE, Fokker-Planck, stochastic control, tumor growth, Gompertz, bang-bang, chance constraint, CVaR, Pareto, CV zoning, reviewer feedback, cover letter, Monte Carlo verification, references, or asks to continue/extend/review Paper 1, Paper 2, TumorTwin or related manuscripts. Use this skill even without explicit paper keyword when the task is about formal mathematical content, numerical experiments for publication, verifying theorems, or preparing academic artifacts.
---

# Academic Paper Writer (Personal — Stefanos/AGEL AI)

A skill encoding the actual workflow that worked across the TumorTwin Paper 1 and Paper 2 sessions. It's personal: it assumes Stefanos's toolchain (LaTeX with Computer Modern, Python + FEniCS/FiPy-style solvers, SLSQP optimization, Monte Carlo verification, Zenodo publication path) and his voice (bilingual Greek/English, first-principles rigor, reviewer-mode self-scrutiny, honest scope admission).

## Core principles (learned the hard way)

Four rules that came from actual mistakes in the Paper 2 sessions:

1. **Numerical verification BEFORE proof writing.** The SDE sign error in Appendix A was caught by Monte Carlo, not by proofreading. Any time a proof claims something testable (FOSD ordering, monotonicity, convergence rate, invariance), run a numerical check before writing the proof. If the numerics disagree with the intuition, the intuition is wrong, not the numerics.

2. **Reference verification with title+DOI+venue every time.** Memory is unreliable for citations. The Maier 2020 vs 2021 confusion and Padmanabhan 2017 vs 2020 confusion both cost time and risked embarrassment. Never paste a citation from memory — always web-search and triangulate (title + DOI + venue + year) before inserting into the paper.

3. **Reviewer-mode pass separate from writing pass.** After finishing a section, read it with reviewer eyes, not author eyes. Look for: sign errors, undefined symbols, unstated hypotheses, gaps between lemma and theorem, claims that go beyond what was proven. This pass found the Lagrangian Part 2 issue — fixed-λ greedy doesn't reproduce structured bang-bang — before it became a published false claim.

4. **Honest scope admission.** When numerical experiments don't support a theoretical claim, admit it in the paper. The Paper 2 A.7.3 Lagrangian limitation is honest rather than false-confident. Reviewers respect this; they punish the opposite. If you find yourself mentally reframing a claim to sound stronger than the evidence allows, you're about to make a reviewer-bait mistake.

## When to use this skill

Trigger on these patterns (bilingual):

- "Συνέχισε το άρθρο / Continue the paper"
- "Γράψε το theorem / Write the theorem"
- "Έλεγξε την απόδειξη / Check the proof"
- "Verify numerically / Επιβεβαίωσε αριθμητικά"
- "Ενημέρωσε τις references / Update references"
- "Self-review / Κάνε reviewer pass"
- "Cover letter για [journal]"
- "Στείλε το στο Zenodo / Submit to Zenodo"
- "Continue paper2 session"
- Any mention of Paper 1, Paper 2, TumorTwin, or `gompertz-fpe-therapy`

Also trigger when Stefanos attaches a `.tex`, `.pdf` with academic content, or references prior session transcripts at `/mnt/transcripts/`.

## Workflow

The skill encodes six modes. Each mode has a reference file with detailed instructions. Read the relevant reference file when entering that mode.

### Mode 1: Starting or continuing a paper

Read `references/latex-template.md` for the exact LaTeX format spec (matches Paper 1 v5 and Paper 2 aesthetic). Key points up front: pdflatex (not XeLaTeX), Computer Modern fonts, centered title, bold numbered sections, amsmath+mathtools+hyperref packages, 1-inch margins.

**Never use ReportLab.** This was tried once in Paper 2 and had to be redone — academic papers go in LaTeX.

For drafts where full LaTeX compilation is overkill (e.g., quick outlines, section planning, Notion notes), Markdown fallback is acceptable. But final paper output is always LaTeX with a successful pdflatex compile.

### Mode 2: Writing a theorem with proof

Read `references/theorem-structure.md` for the proven structure:

1. Formal statement (narrow scope, explicit hypotheses, one-line conclusion)
2. Proof outline (high-level strategy in 2-3 sentences)
3. Supporting lemmas (each self-contained, numerically verifiable if possible)
4. Main proof (combining lemmas)
5. Numerical cross-check remark (validates the proof against FEM/MC simulation)
6. Scope remark (what the theorem does NOT claim — crucial for reviewer defense)

Before writing anything formal, run a numerical check of the intended claim. If the numerics don't match, the proof outline is wrong.

### Mode 3: Numerical verification

Read `references/numerical-verification.md` for the Monte Carlo pattern that caught the sign error. Core pattern: compute the same quantity two ways (FEM solver + direct Monte Carlo) with parameters from Paper 1, and require agreement within expected error. Scripts go in `/tmp/verify_*.py`.

Always use Paper 1's true parameters as defaults: `a=0.1, b=0.05, σ=0.02, y0=5.0, T=8.0, Δt=1.0, n_epochs=8, C_max=0.08, B=0.32, δ=1.15, ε=0.05`. Random seed always `2025`.

### Mode 4: Reference verification and insertion

Read `references/reference-verification.md` for the checklist. Summary:

- Every citation needs web_search confirmation of title+DOI+venue+year
- Never trust memory for author names or years
- Common pitfalls already identified: Maier has two similar papers (2020 DA-only, 2021 RL+DA combined — almost always the 2021 is the intended one); Padmanabhan is 2017 (Math Biosci) not 2020; Roy, Pan & Pal 2022 is the FP-constrained oncology paper (J Math Biol 84:23)
- Bibliography format matches Paper 2: numbered list with hanging indent, DOI as hyperlink when available

### Mode 5: Self-review (reviewer mode)

Read `references/self-review-checklist.md`. After writing any substantive section, run through the checklist before declaring it done. This is a DIFFERENT pass from writing — do it as a separate conversation turn, with the mindset of "what would a hostile reviewer catch here?"

The Lagrangian scope issue and the SDE sign error were both caught in this pass. It's worth 15-20 minutes every time.

### Mode 6: Honest scope admission

Read `references/honest-scope-admission.md` for the patterns that worked in Paper 2. Summary: when a theorem doesn't cover everything you'd hoped, say so explicitly in a "Scope of this result" subsection. Reviewers respect admissions of limitation; they punish overclaiming.

## Notion paper trail

Every substantive discovery, bug fix, scope change, or numerical verification goes into Notion under the `TumorTwin Paper` parent (ID `345b29ce-3d00-81dc-aa14-cbcb852ca73a`). This preserves the reasoning trail across sessions and is the mechanism by which prior sessions are compactable.

When starting a new paper-related conversation, check `/mnt/transcripts/journal.txt` and recent Notion pages under the TumorTwin Paper parent for context from prior sessions.

## Submission pipeline

The three-artifact pipeline (Paper 1, Paper 2, `gompertz-fpe-therapy`) is documented in the Notion page "Publishing roadmap — Zenodo + GitHub timeline" (ID `346b29ce-3d00-819e-a6cb-d3f0ae5e6163`). Key decision points:

- **Paper 1** → Zenodo preprint (CC-BY-4.0, linked to ORCID 0000-0001-7417-2444)
- **Paper 2** → Zenodo AFTER external review + journal submission
- **gompertz-fpe-therapy** → GitHub (MIT) + Zenodo via integration

Preprint policies for Elsevier (Computers in Biology and Medicine) and most target journals allow Zenodo preprints. Verify policy per journal before submission.

## Paper file locations

- Paper 1 v5 PDF: `/mnt/user-data/uploads/Paper1_FPE_FEM_Tumor_Growth_v5.pdf`
- Paper 2 LaTeX source: `/home/claude/paper2_latex/paper2_skeleton.tex`
- Paper 2 PDF output: `/mnt/user-data/outputs/paper2_skeleton.pdf`
- `gompertz-fpe-therapy` package: `/home/claude/gompertz-fpe-therapy/`
- LaTeX template for new papers: `assets/paper_template.tex` (in this skill folder)
- Verification script template: `assets/verification_template.py` (in this skill folder)

## Language convention

- Stefanos communicates in Greek and English interchangeably. Match his register.
- Final paper output is always English (target journals are English-language).
- Drafts, Notion notes, and intermediate commentary can be either language.
- Never translate Stefanos's Greek prompts — respond in the language he's writing in.

## Stop conditions

Don't over-engineer. If the paper is at 94% and Stefanos is tired, the right answer is "submit as-is after external review" — not "let me add three more sections". The Day 2 session explicitly ended with this principle: the value of incremental work decreases sharply after the core claims are solid.

Signs it's time to stop a session:
- Stefanos says "συνέχισε" with no specific target
- All explicit TODO items are done
- Recent work is adding marginal polish, not new substance
- Session has run long and fatigue risk is increasing

In these cases, summarize status, update Notion, and propose "stop here" as the top option.
