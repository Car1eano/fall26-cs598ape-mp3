# Recorded experiment data

This directory is included in the repository. The larger working `results/`
directory remains local and ignored by Git.

- `measurements.csv`: 36 individual ordinary runs at size 1001.
- `summary.csv`: 21 version/thread settings, with sample counts, arithmetic means,
  observed ranges, sample standard deviations, speedup over the original single
  run, and runtime reduction relative to each listed parent configuration.
- `measurement-records.json`: copies of the included original metrics and their
  source locations. Metadata hashes are in `measurements.csv`.
- `excluded-runs.csv`: recorded timing/profiling, other-size, full-grid dump, and
  packaging runs excluded from the performance comparison.
- `methodology.json`: measurement definitions and limitations.
- `validation-summary.json`, `memory-summary.json`: the completed full-grid and
  memory checks, including tool limitations and runtime allocations.
- `vectorization.json`: saved compiler evidence from the two SIMD/native designs.
- `profiling.json`: original and A-symmetry CPU-cycle samples, plus original phase
  timings. These instrumented times are excluded from the benchmark averages;
  sampling percentages are CPU-cycle weights, not fractions of wall time.

The original has one ordinary sample; most settings have two and simplified core
has three. A blank sample SD means only one sample is available. Min–max whiskers
are observed ranges, not confidence intervals. The SIMD directive and native CPU
flags were tested together. Missing fields from early records remain blank.

## Rebuild tables from local records

When the original working `results/` directory is available:

```bash
python3 tools/export_results.py
```

Export rechecks every included PNG against `identity-ref.png`. Export does not
execute any sandpile version. The saved CSV files are sufficient to regenerate
the figures without the working results directory.

## Regenerate the figures

Plotting uses Matplotlib; it is an optional dependency for regenerating figures,
separate from running the C program or timing experiments. Figures were generated
with Python 3.12.15, Matplotlib 3.11.2, and NumPy 2.5.4.

From the repository root, use Python 3.12 or newer:

```bash
sudo apt-get install python3-venv
python3 -m venv /tmp/mp3-plot-env
/tmp/mp3-plot-env/bin/python -m pip install -r tools/plot-requirements.txt
MPLCONFIGDIR=/tmp/mp3-matplotlib /tmp/mp3-plot-env/bin/python tools/plot_results.py
```

This writes PNG previews and vector PDFs in `figures/`, and the tables and
interpretation in [`docs/results.md`](../docs/results.md). The exact package
versions are recorded in `tools/plot-requirements.txt`.
