# MP3 report

Author: Carleano Chang.

- `report.tex`: ACM SIGPLAN source using the `acmart` class with `sigplan,nonacm`.
- `report.pdf`: compiled report, three pages including references.
- `figures/stages.pdf` and `figures/branches.pdf`: figures sized for a single column.
- `make_figures.py`: regenerate figures from the committed measurement CSV.

## Build

From this directory, use a LaTeX installation with `acmart` and its dependencies:

```bash
latexmk -pdf report.tex
```

Alternatively, use Tectonic (tested with version 0.17.0):

```bash
tectonic report.tex
```

References are defined in `report.tex`; no separate BibTeX file is needed.
For Overleaf, upload `report.tex` and `figures/`, then select `report.tex` as the
main file. Compiling the paper is separate from building the sandpile program.

## Figures and evidence

The included figures use `data/measurements.csv`; no benchmark is rerun.
To regenerate them from the repository root with the optional plotting
dependencies installed:

```bash
python mp3-report/make_figures.py
```

Package versions and optional plotting-environment instructions are in
`tools/plot-requirements.txt` and `data/README.md`. The script writes vector PDFs
and ignored PNG previews.

The reported times are arithmetic means of recorded complete-process timings,
including PNG output. The original has one ordinary timing sample; the selected
final version has two. Instrumented and packaging checks are excluded from means.
`data/summary.csv`, `docs/results.md`, and the validation summaries contain the
underlying numbers and limitations.
