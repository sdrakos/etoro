# LaTeX Template Specification

The exact format used in Paper 1 v5 and Paper 2. Violating this format (e.g. using ReportLab, Helvetica, or XeLaTeX with different fonts) breaks aesthetic consistency across the TumorTwin paper series and must be avoided.

## Engine and packages

- **Engine:** `pdflatex` (not XeLaTeX or LuaLaTeX)
- **Document class:** `article` with `11pt` and `a4paper` options
- **Margins:** 1 inch on all sides (`geometry` package)
- **Fonts:** Computer Modern (LaTeX default) — do NOT load any font-changing package
- **Required packages:** `amsmath`, `mathtools`, `amssymb`, `amsthm`, `graphicx`, `hyperref`, `booktabs`, `geometry`, `xcolor`

## Preamble template

```latex
\documentclass[11pt,a4paper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath, mathtools, amssymb, amsthm}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage[colorlinks=true, linkcolor=blue, citecolor=blue, urlcolor=blue]{hyperref}

\theoremstyle{plain}
\newtheorem{theorem}{Theorem}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{proposition}[theorem]{Proposition}
\newtheorem{corollary}[theorem]{Corollary}

\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{remark}[theorem]{Remark}

% Custom todo box for in-progress items
\newcommand{\todo}[1]{\vspace{0.3em}\noindent\fbox{\parbox{0.95\textwidth}{\textit{\textbf{Draft note:} #1}}}\vspace{0.3em}}
```

## Title block

```latex
\title{\textbf{Paper Title Goes Here:\\ Subtitle If Present}}
\author{Stefanos Drakos\\
\small{AGEL AI I.K.E., Rhodes, Greece}\\
\small{ORCID: 0000-0001-7417-2444}}
\date{\today}

\begin{document}
\maketitle
```

The title is centered, bold, with line break between main and subtitle. Author line has affiliation and ORCID in small font.

## Abstract

```latex
\begin{abstract}
One-paragraph summary, roughly 200-300 words. State the problem, the approach, the key contribution, and one headline result. End with a sentence locating the paper relative to prior work (e.g., "These results extend the framework of [X] by introducing [Y]").
\end{abstract}
```

## Section structure

Sections are numbered with bold titles. Use `\section*{}` only for unnumbered sections like abstract and references.

```latex
\section{Introduction}
\label{sec:intro}

Text of introduction, typically 3-5 paragraphs. Locate the problem, review prior work, state contribution, outline paper.

\section{Model and Notation}
\label{sec:model}

Introduce the SDE/FPE/model. Use display equations freely but number only those referenced later.
```

Numbered equations use `equation` environment with `\label{eq:name}` for cross-references:

```latex
\begin{equation}
\frac{\partial P}{\partial t} = -\frac{\partial}{\partial y}(\mu(y,t) P) + \frac{1}{2}\frac{\partial^2}{\partial y^2}(D(t) P)
\label{eq:fpe}
\end{equation}
```

## Theorem environment usage

Theorems are numbered globally (not per-section) for clarity across long papers:

```latex
\begin{theorem}[Short descriptive name]
\label{thm:name}
Formal statement with explicit hypotheses and conclusion.
\end{theorem}

\begin{proof}
Proof body. End with \qed (automatic).
\end{proof}
```

Lemmas, propositions, corollaries share the counter with theorems. Remarks and definitions use the same counter (for consistency with Paper 2).

## Reference list format

Paper 2 uses a custom `list` environment for references rather than `thebibliography`:

```latex
\section*{References}

\begin{list}{}{\leftmargin 2em \itemindent -2em \itemsep 4pt}

\item Albano, G., \& Giorno, V.\ (2006). A stochastic model in tumor
growth. \emph{Journal of Theoretical Biology} 242(2):329--336.
\href{https://doi.org/10.1016/j.jtbi.2006.03.001}{doi:10.1016/j.jtbi.2006.03.001}

\item Lo, C.\ F.\ (2007). Stochastic Gompertz model of tumour cell
growth. \emph{Journal of Theoretical Biology} 248(2):317--321.
\href{https://doi.org/10.1016/j.jtbi.2007.04.024}{doi:10.1016/j.jtbi.2007.04.024}

\end{list}
```

Format notes:
- Authors: Last, F.\ M.\ (with escaped periods to prevent LaTeX from adding extra spaces)
- Journal: `\emph{}` italics
- Volume and issue: `volume(issue):pages`
- DOI: `\href{https://doi.org/...}{doi:...}` format
- Hanging indent 2em via `\leftmargin 2em \itemindent -2em`

For Paper 2 specifically, references are split into two sublists: primary citations and "Historical and methodological references" (for older Gompertz/MLR foundational work).

## Compilation commands

Two passes minimum for cross-references:

```bash
cd /path/to/paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```

Check output for:
- Exit code 0
- No `! Error` lines in log
- No `Warning: Reference undefined` after second pass

Common issues and fixes:
- **Missing `.aux` data:** Run pdflatex twice
- **Undefined references:** Missing `\label{}` or typo in `\ref{}`
- **Figure not found:** Missing `\usepackage{graphicx}` or wrong path
- **Unicode errors:** pdflatex doesn't support UTF-8 by default — use `\usepackage[utf8]{inputenc}` only if needed (most Greek-text characters stay in Notion commentary, not paper body)

## What NOT to do

- **Never use ReportLab.** Tried in early Paper 2 session, had to redo everything in LaTeX. Waste of time.
- **Never use XeLaTeX or LuaLaTeX** unless a specific reason (font requirements). pdflatex is the baseline.
- **Never load `times`, `helvet`, `fontspec`.** Computer Modern is the house style.
- **Never use `fancyhdr` header/footer decorations** — they clash with the minimalist aesthetic.
- **Never number every equation.** Only number what's referenced later.

## File layout convention

```
/home/claude/paperN_latex/
├── paperN_skeleton.tex      # main source
├── paperN_skeleton.pdf      # compiled output
├── paperN_skeleton.log      # compilation log
├── paperN_skeleton.aux      # cross-reference data
└── figures/                 # any included figures
```

Final outputs go to `/mnt/user-data/outputs/paperN_skeleton.{tex,pdf}` for the user to download.
