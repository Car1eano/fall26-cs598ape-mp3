"""Summarize successful ordinary N=1001 trials; exclude instrumented runs."""
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    groups = defaultdict(list)
    for path in sorted((ROOT / "results").rglob("metrics.json")):
        variant = path.relative_to(ROOT / "results").parts[0]
        if variant.startswith(("perf-", "timing-", "validation-")):
            continue
        result = json.loads(path.read_text())
        if (result.get("grid_size") != 1001 or result.get("status") != "completed"
                or result.get("exit_code") != 0):
            continue
        threads = result.get("openmp_environment", {}).get("OMP_NUM_THREADS") or "1"
        groups[(variant, threads)].append(result["wall_seconds"])
    rows = []
    for (variant, threads), times in groups.items():
        rows.append({"variant": variant, "threads": threads, "runs": len(times),
                     "mean_seconds": statistics.mean(times),
                     "min_seconds": min(times), "max_seconds": max(times),
                     "sample_stddev_seconds": statistics.stdev(times) if len(times) > 1 else ""})
    rows.sort(key=lambda row: row["mean_seconds"])
    with (ROOT / "results/summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
