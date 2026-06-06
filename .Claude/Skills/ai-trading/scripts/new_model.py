#!/usr/bin/env python3
"""Scaffold a new QUANTIQ trading-model project the way paper4 is laid out.

Creates the standard folders (code/, engine/, figures/, tests/, paper/) and drops in the
business-report template so a new model starts wired and consistent.

Usage:
    python new_model.py <name> [--path <output-dir>] [--title "..."] [--year 2026]

Example:
    python new_model.py paper5 --path etoro --title "Διαφοροποιημένη στρατηγική μεταβλητότητας"

Bare-import convention: NO __init__.py in code/ or engine/ (run pytest from inside the dir).
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

SUBDIRS = ["code", "code/tests", "engine", "engine/tests", "figures", "paper"]

GITKEEP_NOTE = "# figures are globally git-ignored (*.png); commit the ones you need with `git add -f`\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold a new QUANTIQ trading-model project.")
    ap.add_argument("name", help="model/project folder name, e.g. paper5")
    ap.add_argument("--path", default=".", help="parent directory to create the project in")
    ap.add_argument("--title", default="Διαφοροποιημένη στρατηγική συναλλαγών παρακολούθησης τάσεων",
                    help="business-report cover title (Greek)")
    ap.add_argument("--year", default="2026", help="report/citation year")
    args = ap.parse_args()

    root = Path(args.path).resolve() / args.name
    if root.exists():
        raise SystemExit(f"refusing to overwrite existing path: {root}")
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "figures" / ".gitkeep").write_text(GITKEEP_NOTE, encoding="utf-8")

    # copy + personalize the business-report template
    template = Path(__file__).resolve().parent.parent / "assets" / "report_template.tex"
    if template.exists():
        tex = template.read_text(encoding="utf-8")
        tex = tex.replace(
            "\\newcommand{\\modeltitle}{Διαφοροποιημένη στρατηγική συναλλαγών παρακολούθησης τάσεων}",
            "\\newcommand{\\modeltitle}{" + args.title + "}")
        tex = tex.replace("(Drakos 2026)", f"(Drakos {args.year})")
        tex = tex.replace("\\newcommand{\\reportdate}{Ιούνιος 2026}",
                          "\\newcommand{\\reportdate}{" + args.year + "}")
        (root / "report_GR.tex").write_text(tex, encoding="utf-8")

    (root / "README.md").write_text(
        f"# {args.name}\n\nQUANTIQ trading model. Follow the `ai-trading` skill pipeline:\n"
        "source paper -> reproduce/critique -> evolve on Yahoo -> honest leak-free backtest -> "
        "eToro engine (demo) -> journal paper -> business report (report_GR.tex).\n\n"
        "Layout: `code/` (features, models, sizing, metrics), `engine/` (cli, adapter, "
        "etoro_backtest), `figures/`, `paper/`, `report_GR.tex`.\n", encoding="utf-8")

    print(f"scaffolded {root}")
    for sub in SUBDIRS:
        print(f"  {args.name}/{sub}/")
    print(f"  {args.name}/report_GR.tex   (edit the metadata lines, then fill + compile with XeLaTeX x2)")
    print(f"  {args.name}/README.md")


if __name__ == "__main__":
    main()
