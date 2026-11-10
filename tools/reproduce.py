"""Build and benchmark selected variants sequentially in a new output directory."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_FLAGS = "-O3 -lm -g -Werror"
# name: (make target, source, executable, additional compiler flags)
VARIANTS = {
    "final": ("all", "sandpile.c", "sandpile.exe", "-fopenmp -march=native"),
    "baseline": ("baseline", "baseline/sandpile.c", "sandpile-baseline.exe", ""),
    "row-bounds": ("row-bounds", "variants/row-bounds-batch.c", "sandpile-row-bounds.exe", "-DSINGLE_TOPPLE"),
    "batch-toppling": ("batch-toppling", "variants/row-bounds-batch.c", "sandpile-batch-toppling.exe", ""),
}
for name in ["flat-padding", "two-phase", "red-black", "row-three-color", "red-black-openmp",
             "row-three-color-symmetry", "red-black-openmp-symmetry", "red-black-openmp-symmetry-simd",
             "row-three-color-symmetry-cyclic", "row-three-color-local-flags", "row-three-color-core-loop",
             "red-black-fused", "red-black-fused-simd", "row-three-color-core-loop-lto"]:
    source = "row-three-color-core-loop" if name.endswith("-lto") else name
    extra = "" if name in ["flat-padding", "two-phase", "red-black"] else "-fopenmp"
    if name.endswith("-simd"):
        extra += " -march=native"
    if name.endswith("-lto"):
        extra += " -flto"
    VARIANTS[name] = (name, "variants/" + source + ".c", "sandpile-" + name + ".exe", extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", nargs="+", choices=VARIANTS, default=["final"])
    parser.add_argument("--size", type=int, default=1001)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--threads", type=int, choices=[1, 2, 4], default=4,
                        help="Team size for OpenMP variants; serial variants always use one thread")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.size < 1 or args.runs < 1:
        parser.error("size and runs must be positive")
    if len(set(args.variant)) != len(args.variant):
        parser.error("variant names must be unique")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "running", "stage": "preparing", "results": []}

    def save(stage):
        state["stage"] = stage
        (output / "status.json").write_text(json.dumps(state, indent=2) + "\n")
        print(stage, flush=True)

    try:
        for variant in args.variant:
            target, source, executable, extra = VARIANTS[variant]
            threads = args.threads if "-fopenmp" in extra else 1
            directory = output / variant
            directory.mkdir()
            save("building " + variant)
            with (directory / "build.log").open("w") as log:
                subprocess.run(["make", "-B", target], cwd=ROOT, stdout=log, stderr=log, check=True)
            times = []
            for run in range(1, args.runs + 1):
                save(f"running {variant}, threads={threads}, run={run}")
                trial = directory / f"threads-{threads}/n{args.size}/run-{run:02d}"
                subprocess.run([sys.executable, str(ROOT / "tools/run_trial.py"),
                                "--binary", str(ROOT / executable), "--source", str(ROOT / source),
                                "--size", str(args.size), "--threads", str(threads),
                                "--build-flags=" + BASE_FLAGS + (" " + extra if extra else ""),
                                "--output", str(trial)], cwd=ROOT, check=True)
                metrics = json.loads((trial / "metrics.json").read_text())
                if args.size == 1001 and not metrics.get("matches_reference_png"):
                    raise RuntimeError(f"PNG reference mismatch: {trial}")
                if "-fopenmp" in extra:
                    if (trial / "stderr.log").read_text().splitlines() != [f"openmp_threads={threads}"] * 2:
                        raise RuntimeError(f"Unexpected OpenMP team size: {trial}")
                times.append(metrics["wall_seconds"])
            state["results"].append({"variant": variant, "grid_size": args.size,
                                     "threads": threads, "runs": len(times),
                                     "mean_seconds": statistics.mean(times),
                                     "min_seconds": min(times), "max_seconds": max(times),
                                     "sample_stddev_seconds": statistics.stdev(times) if len(times) > 1 else ""})
            with (output / "summary.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(state["results"][0]))
                writer.writeheader()
                writer.writerows(state["results"])
        state["status"] = "completed"
        save("all requested trials completed")
    except Exception as error:
        state.update(status="failed", error=str(error))
        save("stopped; inspect logs before rerunning with a new output directory")
        raise


if __name__ == "__main__":
    main()
