# Journal paper + business report

Every model ships two write-ups: a **journal paper** (peer-grade, with a genuine novel
contribution) and a **business report** (non-technical, for executives/investors). Different
audiences, different voice.

## The journal paper

Use the **`academic-paper-writer`** skill (its rules: numerical verification BEFORE writing a
claim; reference verification with title+DOI+venue; a separate reviewer-mode pass; honest scope
admission). Existing exemplars: `paper3/paper_skeleton.tex` (honest null) and
`paper4/paper_skeleton.tex` (the dead→alive momentum arc).

**Originality is required each time.** Before writing, state in one sentence what is new relative to
the source paper. Acceptable contributions:
- a **new mechanism** (e.g. belief-state features feeding a deep momentum net);
- a **new combination** of known parts that is shown to help (and ablated to prove it);
- an **honest negative result** on a widely-assumed edge (a null *is* a contribution — cf. paper3);
- a **deployment artifact** (a demo-verified live engine on real broker prices).

**Structure:** narrow formal claims → method → leak-free evaluation → results with NW-t / DSR /
durability → **explicit "Scope of this result"** subsection saying what it does NOT claim. Embed
figures with `\usepackage{float}` + `[H]`. Reviewers respect admitted limitations and punish
overclaiming.

**Citation style in any prose that references our own paper:** cite by **full title** followed by
`(Drakos <year>)` — never an internal label like "paper4".

## The business report (non-technical, LaTeX/PDF)

Audience: business people and investors. **Serious, non-metaphorical** prose — no surfer/wave
analogies, no emoji, no AI-template bullet spam. Greek by default (unless the user asks otherwise).
Template: **`assets/report_template.tex`** (copy it next to the model's `figures/`).

Build recipe (matches the existing `paper4/report_GR.pdf`):
- **XeLaTeX** + `fontspec` with `DejaVu Serif` / `DejaVu Sans`. **Required:** `polyglossia` with
  `\setmainlanguage{greek}` — without Greek hyphenation, justified text overflows the right margin.
  Add `\tolerance=2500` + `\emergencystretch=3em` as a safety net. Use the unicode `€` directly
  (eurosym is not installed). Compile **twice**.
- **Cover page:** `QUANTIQ` large, `Deep Learning Trading` subtitle, a serious document title,
  signed `Dr. Stefanos Drakos`, QUANTIQ / AGEL AI, month/year.
- **Contents:** what the system does, how it trains (the feature set, rules vs ML, leak-free
  walk-forward), how it runs live in QUANTIQ on eToro (signal→mapping→rebalance→demo, when positions
  close, the risk dial + vol-method), then **all results with tables AND figures** (real eToro
  prices, diversity, long vs long/short, crypto, vol ladder, vol-method comparison, beat-buy&hold,
  ML, sizing, why it works / where it's dead, crisis allocation), and honest caveats.
- Cite the paper by full title `(Drakos <year>)` via a reusable `\paperref` macro (intro + footer).
- Pull headline numbers from the model's `results_*.json` so the report stays consistent with the code.

### Render-to-PNG for visual QA (no pdftoppm in the Read tool)

```python
import fitz                       # PyMuPDF is available
d = fitz.open("report_GR.pdf")
for i in (0, 1): d[i].get_pixmap(dpi=120).save(f"/tmp/p{i+1}.png")
```
Then Read the PNGs. Check: 0 overfull boxes, 0 missing glyphs, cover + intro + a figure page.

## Commit / publish

Clean `git commit -m` (**no Co-Authored-By**). Figures are globally git-ignored — `git add -f`.
Push uses `GIT_HUB_TOKEN` from `back/.env`; **mask the token** in any output. Paper PDFs and
`report_*.pdf` are tracked (not ignored). Optionally log the discovery trail to Notion under the
project parent.
