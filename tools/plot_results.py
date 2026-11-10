"""Regenerate report figures and results notes from the bundled CSV measurements."""
import argparse
import csv
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREEN = "#26739b", "#b96b28", "#22805a"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "figures")
    parser.add_argument("--notes", type=Path, default=ROOT / "docs/results.md")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.data / "summary.csv").open() as file:
        rows = list(csv.DictReader(file))
    with (args.data / "measurements.csv").open() as file:
        measurements = list(csv.DictReader(file))
    summaries = {}
    samples = {}
    for row in rows:
        row["threads"], row["runs"] = int(row["threads"]), int(row["runs"])
        for field in ["mean_seconds", "min_seconds", "max_seconds", "speedup_vs_original_single_run"]:
            row[field] = float(row[field])
        summaries[row["variant"], row["threads"]] = row
    for row in measurements:
        samples.setdefault((row["variant"], int(row["threads"])), []).append(float(row["wall_seconds"]))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "savefig.facecolor": "white"})

    def save(fig, name):
        fig.savefig(args.output / (name + ".png"), dpi=200, bbox_inches="tight")
        fig.savefig(args.output / (name + ".pdf"), bbox_inches="tight",
                    metadata={"CreationDate": None, "ModDate": None})
        plt.close(fig)

    def observation(ax, key, y, color):
        row = summaries[key]
        mean, lo, hi = (row[field] for field in ["mean_seconds", "min_seconds", "max_seconds"])
        ax.errorbar(mean, y, xerr=[[mean - lo], [hi - mean]], fmt="D", color=color,
                    ecolor="#3c444b", markersize=5, capsize=3, zorder=4)
        values = samples[key]
        offsets = [0] if len(values) == 1 else [(i - (len(values) - 1) / 2) * .13 for i in range(len(values))]
        ax.scatter(values, [y + offset for offset in offsets], s=14, color="#262d34", zorder=5)

    # Overview includes every algorithm/build variant; thread scaling has its own figure.
    overview = [row for row in rows if row["threads"] == 4 or row["variant"] not in ["row-three-color", "red-black-openmp"]]
    fig, ax = plt.subplots(figsize=(11.4, 8))
    for y, row in enumerate(overview):
        color = GREEN if row["variant"] == "red-black-fused-simd" else BLUE if row["branch"] == "A" else ORANGE if row["branch"] == "B" else "#87939f"
        ax.barh(y, row["mean_seconds"], height=.57, color=color, alpha=.24)
        observation(ax, (row["variant"], row["threads"]), y, color)
        ax.text(row["max_seconds"] + 12, y, f'{row["mean_seconds"]:.2f} s  (n={row["runs"]})', va="center", fontsize=9)
    ax.set_yticks(range(len(overview)), [f'{row["label"]} [{row["threads"]}T]' for row in overview])
    ax.invert_yaxis()
    ax.set_xlim(0, 1080)
    ax.set_xlabel("Complete process wall time (seconds; lower is better)")
    ax.set_title("All optimization variants: 1001 × 1001", loc="left", weight="bold", pad=14)
    ax.grid(axis="x", alpha=.17)
    ax.set_axisbelow(True)
    fig.text(.02, .025, "T: threads. Diamonds: means. Dots: individual runs. Whiskers: observed min–max, not confidence intervals.\nOriginal and two serial update experiments have n=1; no variability estimate is available for them.", fontsize=9)
    fig.subplots_adjust(left=.36, right=.98, top=.92, bottom=.12)
    save(fig, "runtime_overview")

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.3))
    branches = [
        ("A: three row groups", BLUE, [
            ("row-three-color-symmetry", "Symmetry"),
            ("row-three-color-symmetry-cyclic", "Cyclic rows"),
            ("row-three-color-local-flags", "Local flags"),
            ("row-three-color-core-loop", "Simplified core"),
            ("row-three-color-core-loop-lto", "Core + LTO")]),
        ("B: red-black updates", ORANGE, [
            ("red-black-openmp-symmetry", "Symmetry"),
            ("red-black-openmp-symmetry-simd", "Two-phase SIMD/native"),
            ("red-black-fused", "Fused update"),
            ("red-black-fused-simd", "Fused + SIMD/native")])]
    for ax, (title, color, entries) in zip(axes, branches):
        labels = []
        for y, (variant, label) in enumerate(entries):
            row = summaries[variant, 4]
            observation(ax, (variant, 4), y, GREEN if variant == "red-black-fused-simd" else color)
            ax.text(row["max_seconds"] + .8, y, f'{row["mean_seconds"]:.2f}', va="center", fontsize=9)
            labels.append(f'{label} (n={row["runs"]})')
        ax.set_yticks(range(len(entries)), labels)
        ax.invert_yaxis()
        ax.set_xlim(20, 65)
        ax.set_ylim(len(entries) - .5, -.5)
        ax.set_xlabel("Wall time (seconds)")
        ax.set_title(title, loc="left", weight="bold")
        ax.grid(axis="x", alpha=.17)
    fig.suptitle("Later optimizations at 4 threads, 1001 × 1001", y=1.02, fontsize=13)
    handles = [Line2D([], [], marker="D", color="none", markerfacecolor=BLUE, markeredgecolor=BLUE, label="Mean"),
               Line2D([], [], marker="o", color="none", markerfacecolor="#262d34", label="Individual run"),
               Line2D([], [], color="#3c444b", marker="|", label="Observed min–max")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
    fig.tight_layout(rect=[0, .11, 1, 1])
    save(fig, "late_optimizations")

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    for variant, label, color in [("row-three-color", "A: row groups", BLUE),
                                  ("red-black-openmp", "B: red-black", ORANGE)]:
        keys = [(variant, threads) for threads in [1, 2, 4]]
        means = [summaries[key]["mean_seconds"] for key in keys]
        baseline = means[0]
        for ax, speedup in [(axes[0], False), (axes[1], True)]:
            values = [baseline / value if speedup else value for value in means]
            ax.plot([1, 2, 4], values, marker="D", color=color, label=label, linewidth=1.5, markersize=5)
            for key, x in zip(keys, [1, 2, 4]):
                individual = [baseline / value if speedup else value for value in samples[key]]
                ax.scatter([x] * len(individual), individual, color=color, s=13, zorder=4)
                row = summaries[key]
                lo = baseline / row["max_seconds"] if speedup else row["min_seconds"]
                hi = baseline / row["min_seconds"] if speedup else row["max_seconds"]
                ax.vlines(x, lo, hi, color=color, linewidth=2)
            ax.set_xticks([1, 2, 4])
            ax.set_xlabel("OpenMP threads")
            ax.grid(alpha=.17)
            ax.set_xlim(.8, 4.2)
    axes[0].set_ylim(0, 390)
    axes[0].set_ylabel("Wall time (seconds)")
    axes[0].set_title("Runtime")
    axes[1].plot([1, 2, 4], [1, 2, 4], linestyle="--", color="#8b949c", label="Ideal scaling")
    axes[1].set_ylim(.8, 4.2)
    axes[1].set_ylabel("Speedup vs. same branch at 1 thread")
    axes[1].set_title("Parallel scaling")
    axes[1].legend(frameon=False, fontsize=9)
    fig.suptitle("Thread scaling before symmetry, 1001 × 1001", fontsize=13)
    fig.text(.02, .015, "1- and 2-thread settings: n=1 each. 4-thread settings: n=2 each. Ranges show observed min–max.", fontsize=9)
    fig.tight_layout(rect=[0, .06, 1, .98])
    save(fig, "thread_scaling")

    original = summaries["original", 1]
    final = summaries["red-black-fused-simd", 4]
    core = summaries["row-three-color-core-loop", 4]
    fused = summaries["red-black-fused", 4]
    def mean(variant, threads=4):
        return summaries[variant, threads]["mean_seconds"]
    def increase(child, parent):
        return 100 * (child / parent - 1)
    table = ["| Version | Threads | n | Mean (s) | Min–max (s) | Sample SD (s) | Speedup |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        sd = summaries[row["variant"], row["threads"]]["sample_stddev_seconds"]
        sd = f"{float(sd):.3f}" if sd else "—"
        label = row["label"]
        if row["variant"] == "red-black-fused-simd":
            label = "**" + label + "**"
        table.append(f'| {label} | {row["threads"]} | {row["runs"]} | {row["mean_seconds"]:.3f} | {row["min_seconds"]:.3f}–{row["max_seconds"]:.3f} | {sd} | {row["speedup_vs_original_single_run"]:.2f}× |')
    notes = f'''# Recorded performance results

The final implementation takes **{final["mean_seconds"]:.3f} seconds** on average
over two ordinary 1001 × 1001 runs, versus the original single ordinary run of
{original["mean_seconds"]:.3f} seconds: **{final["speedup_vs_original_single_run"]:.2f}× speedup**,
or {100 * (1 - final["mean_seconds"] / original["mean_seconds"]):.2f}% less runtime.
The final observed range is {final["min_seconds"]:.3f}–{final["max_seconds"]:.3f} seconds;
sample SD is {float(final["sample_stddev_seconds"]):.3f} seconds. The later clean-copy
verification run is excluded from these averages.

## Measurement scope

- [Bundled measurements](../data/measurements.csv): {len(measurements)} ordinary runs, {len(rows)} version/thread settings.
- [Summary](../data/summary.csv), [original metadata](../data/measurement-records.json),
  [exclusions](../data/excluded-runs.csv), and [methodology](../data/methodology.json).
- All runs use size 1001. Time covers the complete program and PNG output;
  compilation, perf, phase timers, full-grid dumps, and packaging validation are excluded.
- Arithmetic means use all available ordinary runs, without excluding a warm-up.
  Most settings have two samples; simplified core has three. Single-sample settings
  have no estimated variability. Whiskers are observed min–max, not confidence intervals.
- Every included PNG was rechecked byte for byte against `identity-ref.png` during export.
  Early metadata fields that were not recorded remain blank; they are not reconstructed.
- See [reproduction instructions](experiments.md) for the course VM and build options.

## All versions

![Runtime overview](../figures/runtime_overview.png)

[Vector PDF](../figures/runtime_overview.pdf)

{chr(10).join(table)}

Speedup divides the original **single** ordinary time by each row's mean. These
values do not establish statistical significance. Trials were collected in development
order on a shared VM; host load and scheduling were not randomized or controlled.

## Later branch comparisons

![Later optimizations](../figures/late_optimizations.png)

[Vector PDF](../figures/late_optimizations.pdf)

- A's simplified core averages {core["mean_seconds"]:.3f} seconds. Its LTO build is
  {100 * (1 - mean("row-three-color-core-loop-lto") / core["mean_seconds"]):.2f}% lower on average,
  a small observed difference with only two versus three samples.
- B's fused update alone averages {fused["mean_seconds"]:.3f} seconds, but ranges from
  {fused["min_seconds"]:.3f} to {fused["max_seconds"]:.3f}. Its apparent small gain over
  B symmetry is inconclusive given this observed spread.
- Fused SIMD/native reduces runtime by {100 * (1 - final["mean_seconds"] / fused["mean_seconds"]):.2f}%
  relative to fused scalar, and {100 * (1 - final["mean_seconds"] / core["mean_seconds"]):.2f}%
  relative to A's simplified core. The SIMD directive and `-march=native` were enabled
  together, so their separate contributions have not been measured. The saved
  [compiler evidence](../data/vectorization.json) confirms vectorized stabilization loops.
- Padding alone increases runtime by {increase(mean("flat-padding", 1), mean("batch-toppling", 1)):.2f}%;
  global two-phase is {mean("two-phase", 1) / mean("flat-padding", 1):.2f}× slower than padding.
  These unsuccessful intermediate designs were retained as foundations for later changes.
- Local termination flags increase runtime by {increase(mean("row-three-color-local-flags"), mean("row-three-color-symmetry-cyclic")):.2f}%;
  SIMD/native on the earlier B two-phase design increases it by
  {increase(mean("red-black-openmp-symmetry-simd"), mean("red-black-openmp-symmetry")):.2f}%.
  Fewer barriers or vectorized loops alone did not guarantee an end-to-end gain.

Precomputed bounds avoid repeated geometry tests in the stabilization sweeps.
Batch toppling removes multiple groups of four grains per visit. Symmetry reduces
the simulated rows for odd sizes, with explicit center-row handling. Row grouping
and red-black phases arrange independent work for OpenMP; fused red-black updates
also make same-color cells independent within the vectorized loop. These explain
the intended mechanisms. Wall times alone do not isolate the cache, branch, or
synchronization cost of each design.

The earlier [profiling evidence](../data/profiling.json) puts 99.97% of the original
sampled CPU-cycle weight in `stabilize`. The later profile is of A symmetry,
not the final fused SIMD/native version. These profiles guide the optimization
sequence; their times are excluded from the ordinary timing table.

## Thread scaling

![Thread scaling](../figures/thread_scaling.png)

[Vector PDF](../figures/thread_scaling.pdf)

At four threads, A achieves {mean("row-three-color", 1) / mean("row-three-color"):.2f}×
and B achieves {mean("red-black-openmp", 1) / mean("red-black-openmp"):.2f}× relative to
their own single-thread settings. These compare the same algorithm at different
team sizes; they are distinct from speedup over the original algorithm.
Only A and B before symmetry were tested at all three team sizes.

## Correctness evidence

All included PNGs match the reference. The selected final algorithm also matched
the original in every one of 1,002,001 integer cells in two separate 4-thread runs.
[Validation summary](../data/validation-summary.json) and
[memory summary](../data/memory-summary.json) preserve the completed checks.
Valgrind used the same source with AVX-512 disabled; native ASan/UBSan was checked
separately. OpenMP TLS allocations reported as possibly lost/still reachable remain
documented, rather than being presented as zero in every leak category.
'''
    args.notes.parent.mkdir(parents=True, exist_ok=True)
    args.notes.write_text(notes)
    (args.output / "generation.json").write_text(json.dumps({
        "python": platform.python_version(), "matplotlib": matplotlib.__version__,
        "inputs": ["data/summary.csv", "data/measurements.csv"],
        "figures": ["runtime_overview", "late_optimizations", "thread_scaling"],
        "formats": ["png", "pdf"]}, indent=2) + "\n")
    print("Generated three PNG/PDF figures and " + str(args.notes))


if __name__ == "__main__":
    main()
