"""Create column-sized report figures from the committed measurement CSV."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parent / "figures"
BLUE, ORANGE, GREEN = "#26739b", "#b96b28", "#22805a"


def main():
    OUTPUT.mkdir(exist_ok=True)
    with (ROOT / "data/measurements.csv").open() as file:
        rows = list(csv.DictReader(file))
    samples = {}
    for row in rows:
        samples.setdefault((row["variant"], int(row["threads"])), []).append(float(row["wall_seconds"]))
    original = samples["original", 1][0]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.3,
                         "axes.labelsize": 7.5, "xtick.labelsize": 7,
                         "ytick.labelsize": 7.1, "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False})

    def save(fig, name):
        fig.savefig(OUTPUT / (name + ".pdf"), bbox_inches="tight",
                    metadata={"CreationDate": None, "ModDate": None})
        fig.savefig(OUTPUT / (name + ".png"), dpi=230, bbox_inches="tight")
        plt.close(fig)

    entries = [
        ("original", 1, "Original", "#87939f"),
        ("row-bounds", 1, "Row bounds", "#87939f"),
        ("batch-toppling", 1, "Batch toppling", "#87939f"),
        ("row-three-color", 4, "A: OpenMP", BLUE),
        ("red-black-openmp", 4, "B: OpenMP", ORANGE),
        ("row-three-color-symmetry", 4, "A: symmetry", BLUE),
        ("red-black-openmp-symmetry", 4, "B: symmetry", ORANGE),
        ("red-black-fused-simd", 4, "Final fused SIMD", GREEN)]
    fig, ax = plt.subplots(figsize=(3.33, 2.2))
    for y, (variant, threads, label, color) in enumerate(entries):
        values = samples[variant, threads]
        speedup = original / (sum(values) / len(values))
        individual = [original / value for value in values]
        ax.barh(y, speedup, color=color, alpha=.38, height=.63)
        ax.plot([min(individual), max(individual)], [y, y], color="#343b41", linewidth=.8)
        ax.scatter(individual, [y] * len(individual), color=color, s=9, zorder=4)
        ax.text(speedup + .35, y, f"{speedup:.2f}", va="center", fontsize=7)
    ax.set_yticks(range(len(entries)), [entry[2] for entry in entries])
    ax.invert_yaxis()
    ax.set_xlim(0, 29)
    ax.set_xticks([0, 5, 10, 15, 20, 25])
    ax.set_xlabel("Speedup over original single run (×)")
    ax.grid(axis="x", alpha=.17)
    ax.set_axisbelow(True)
    fig.subplots_adjust(left=.34, right=.99, top=.99, bottom=.20)
    save(fig, "stages")

    entries = [
        ("row-three-color-symmetry", "A symmetry", BLUE),
        ("row-three-color-symmetry-cyclic", "A cyclic rows", BLUE),
        ("row-three-color-local-flags", "A local flags", BLUE),
        ("row-three-color-core-loop", "A core", BLUE),
        ("row-three-color-core-loop-lto", "A core + LTO", BLUE),
        ("red-black-openmp-symmetry", "B symmetry", ORANGE),
        ("red-black-openmp-symmetry-simd", "B SIMD/native", ORANGE),
        ("red-black-fused", "B fused", ORANGE),
        ("red-black-fused-simd", "B fused SIMD", GREEN)]
    fig, ax = plt.subplots(figsize=(3.33, 2.55))
    for y, (variant, label, color) in enumerate(entries):
        values = samples[variant, 4]
        mean = sum(values) / len(values)
        offsets = [(i - (len(values) - 1) / 2) * .13 for i in range(len(values))]
        ax.plot([min(values), max(values)], [y, y], color="#343b41", linewidth=1)
        ax.plot(mean, y, marker="D", color=color, markersize=3.5)
        ax.scatter(values, [y + offset for offset in offsets], color=color, s=8, zorder=4)
        ax.text(max(values) + .7, y, f"{mean:.1f}", va="center", fontsize=7)
    ax.axhline(4.5, color="#b8bfc4", linestyle=":", linewidth=.7)
    ax.set_yticks(range(len(entries)), [entry[1] for entry in entries])
    ax.set_ylim(len(entries) - .5, -.5)
    ax.set_xlim(20, 65)
    ax.set_xticks([20, 30, 40, 50, 60])
    ax.set_xlabel("Wall time at 4 threads (seconds)")
    ax.grid(axis="x", alpha=.17)
    fig.subplots_adjust(left=.31, right=.99, top=.99, bottom=.18)
    save(fig, "branches")
    print("Generated report figures from the recorded data; no sandpile runs.")


if __name__ == "__main__":
    main()
