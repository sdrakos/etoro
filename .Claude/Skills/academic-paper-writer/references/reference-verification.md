# Reference Verification

Every citation goes through web_search verification before insertion into the paper. Memory is unreliable — title+DOI+venue+year must be confirmed independently.

## Checklist for each citation

For every citation, verify:

1. **Title** — exact wording, including punctuation and capitalization
2. **All authors** — not just first author, in correct order
3. **Year** — not always what you remember
4. **Venue** — journal name + volume + issue + pages
5. **DOI** — present and valid (clicking it should return the paper)

Typical web_search query: `"<first author last name>" <key topic words> <approximate year>`

Example: `"Maier" reinforcement learning Bayesian assimilation oncology 2021`

Then cross-check with a second search on DOI or PubMed ID to confirm.

## Known confusions (verified during Paper 2 sessions)

### Maier 2020 vs 2021 — TWO papers, different content

**Wrong (2020):** Maier, Hartung, de Wiljes, Kloft, Huisinga. "Bayesian data assimilation to support informed decision-making in individualized chemotherapy." CPT:PSP 9(3):153–164. DOI 10.1002/psp4.12492. *DA-only, no RL.*

**Correct for Paper 2 (2021):** Maier, Hartung, Kloft, Huisinga, de Wiljes. "Reinforcement learning and Bayesian data assimilation for model-informed precision dosing in oncology." CPT:PSP 10(3):241–254. DOI 10.1002/psp4.12588. *Adds RL to DA.*

Paper 2 Discussion §9.2 references the RL+DA combined paper (2021), not the DA-only 2020 paper. If citing "RL + posterior state" — it's 2021.

### Padmanabhan 2017, not 2020

**Correct:** Padmanabhan, Meskin, Haddad. "Reinforcement learning-based control of drug dosing for cancer chemotherapy treatment." Mathematical Biosciences 293:11–20, **2017**. DOI 10.1016/j.mbs.2017.08.004.

There's a 2020 book chapter with similar title ("Reinforcement learning-based control of drug dosing with applications to anesthesia and cancer therapy", Control Applications for Biomedical Engineering Systems, 2020, pp. 251–297) — that's a later review chapter, not the original research paper.

### Yauney & Shah 2018

**Correct:** Yauney, Shah. "Reinforcement Learning with Action-Derived Rewards for Chemotherapy and Clinical Trial Dosing Regimen Selection." Proceedings of the 3rd Machine Learning for Healthcare Conference, PMLR 85:161–226, 2018.

No DOI — PMLR proceedings don't assign DOIs. URL instead: https://proceedings.mlr.press/v85/yauney18a.html

### Roy, Pan & Pal 2022 — FP-constrained cancer therapy

**Correct:** Roy, Pan, Pal. "A Fokker-Planck feedback control framework for optimal personalized therapies in colon cancer-induced angiogenesis." Journal of Mathematical Biology 84(4):23, 2022. DOI 10.1007/s00285-022-01725-3.

Author order matters — Souvik Roy is first author (UT Arlington Mathematics), Zui Pan is second, Suvra Pal is third.

### Karlin & Rubin 1956 — foundational MLR

**Correct:** Karlin, Rubin. "The theory of decision procedures for distributions with monotone likelihood ratio." Annals of Mathematical Statistics 27(2):272–299, 1956. DOI 10.1214/aoms/1177728259.

Cited in Paper 2 as the general MLR-based framing that the spatial-homogeneity-based coupling argument shortcuts.

## Verified reference list (Paper 2 as of April 2026)

Primary citations:

- Albano & Giorno 2006 — J Theor Biol 242(2):329-336
- Albano et al. 2011 — Math Biosci Eng 10(1):13-28 (Albano, Giorno, Román-Román, Torres-Ruiz)
- Albano et al. 2013 — Stat Med 32(1):102-114
- Albano et al. 2020 — Mathematics 8(11):1958 (heteroscedastic Gompertz)
- Chaudhuri et al. 2023 — Journal of Computational Physics, α-superquantile digital twin
- Kapteyn et al. 2021 — Nat Comput Sci 1(5):337-347
- Karlin & Rubin 1956 — Ann Math Stat 27(2):272-299
- Lo 2007 — J Theor Biol 248(2):317-321
- Maier et al. 2021 — CPT:PSP 10(3):241-254
- Padmanabhan et al. 2017 — Math Biosci 293:11-20
- Roy, Pan & Pal 2022 — J Math Biol 84(4):23
- Sargolzaei et al. 2020 — IET Systems Biology 14(6):368-379
- Wu et al. 2025 — npj Digital Medicine 8:195
- Yauney & Shah 2018 — PMLR 85:161-226

Historical/methodological:

- Laird 1964 — Br J Cancer 18(3):490-502
- Norton 1988 — Cancer Research 48(24):7067-7071
- Gerlee 2013 — Cancer Research 73(8):2407-2411

## Bibliography format

Paper 2 uses a custom `list` environment rather than BibTeX:

```latex
\section*{References}

\begin{list}{}{\leftmargin 2em \itemindent -2em \itemsep 4pt}

\item Author, A.\ B., \& Author, C.\ D.\ (YYYY). Title of the paper
in plain text. \emph{Journal Name} volume(issue):pages.
\href{https://doi.org/DOI}{doi:DOI}

\end{list}
```

Conventions:
- Author initials get escaped periods: `A.\ B.\`
- Journal titles in `\emph{}`
- Volume(issue):pages format with no space after colon
- DOI as clickable link via `\href{}{}`
- `\&` between last two authors, not `and`
- Year in parentheses immediately after authors
- Title in plain text (not quoted, not italicized)
- Period at end of title before journal

## Process for adding a reference

1. Search web for `"<author>" <topic keywords> <year>`
2. Confirm title, year, venue from official publisher page or PubMed
3. Retrieve DOI from CrossRef or publisher page
4. Format in the standard bibliography style above
5. Insert in alphabetical order by first author surname
6. Add `\cite{}` or inline `(Author YYYY)` reference in the body

If the DOI is not found after 2 searches, flag as TODO with `\todo{Verify citation: <details>}` and continue. Don't fabricate DOIs.

## When to cite vs when to paraphrase without citation

Cite when:
- Claim is due to someone else (prior art, theorem, formulation)
- Using a technique by name (Pontryagin, Bayesian, FOSD, MLR)
- Comparing to a specific published approach
- Discussing motivation or background

Don't cite for:
- Standard facts (definitions of expectation, variance, normal distribution)
- Widely known mathematical objects (FPE, SDE, Ito's isometry)
- Own prior work from same paper series — use `\S\ref{}` internal cross-reference

## Papers that did NOT make the final cut

Searched for but not included in Paper 2 references (keep this list to avoid re-searching):

- Sutton & Barto RL textbook — general RL reference, not specific to oncology dosing
- Various Martignoni/Jarrett/Hormuth papers — reviewed, less direct relevance than Wu et al. 2025
- MATLAB Toolbox documentation — not academic references
- FEniCS/COMSOL documentation — software documentation, not papers
