"""Export recorded ordinary trials and auditable summaries without running sandpile."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
# identifier, label, branch, parent identifier, parent threads, build target
VERSIONS = [
    ("original", "Original", "Common", None, None, "baseline"),
    ("row-bounds", "Precomputed row bounds", "Common", "original", 1, "row-bounds"),
    ("batch-toppling", "Batch toppling", "Common", "row-bounds", 1, "batch-toppling"),
    ("flat-padding", "Contiguous storage + padding", "B", "batch-toppling", 1, "flat-padding"),
    ("two-phase", "Global two-phase update", "B", "flat-padding", 1, "two-phase"),
    ("red-black", "Serial red-black update", "B", "two-phase", 1, "red-black"),
    ("row-three-color", "A: three row groups + OpenMP", "A", "batch-toppling", 1, "row-three-color"),
    ("red-black-openmp", "B: red-black + OpenMP", "B", "red-black", 1, "red-black-openmp"),
    ("row-three-color-symmetry", "A + symmetry", "A", "row-three-color", 4, "row-three-color-symmetry"),
    ("red-black-openmp-symmetry", "B + symmetry", "B", "red-black-openmp", 4, "red-black-openmp-symmetry"),
    ("red-black-openmp-symmetry-simd", "B symmetry + SIMD/native", "B", "red-black-openmp-symmetry", 4, "red-black-openmp-symmetry-simd"),
    ("row-three-color-symmetry-cyclic", "A symmetry + cyclic scheduling", "A", "row-three-color-symmetry", 4, "row-three-color-symmetry-cyclic"),
    ("row-three-color-local-flags", "A cyclic + local flags", "A", "row-three-color-symmetry-cyclic", 4, "row-three-color-local-flags"),
    ("row-three-color-core-loop", "A cyclic + simplified core", "A", "row-three-color-symmetry-cyclic", 4, "row-three-color-core-loop"),
    ("row-three-color-core-loop-lto", "A simplified core + LTO", "A", "row-three-color-core-loop", 4, "row-three-color-core-loop-lto"),
    ("red-black-fused", "B symmetry + fused update", "B", "red-black-openmp-symmetry", 4, "red-black-fused"),
    ("red-black-fused-simd", "B fused + SIMD/native (final)", "B", "red-black-fused", 4, "red-black-fused-simd"),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_csv(path, records):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    versions = {item[0]: item for item in VERSIONS}
    reference = (ROOT / "identity-ref.png").read_bytes()
    rows, records, excluded = [], [], []
    for path in sorted(args.input.rglob("metrics.json")):
        metadata = json.loads(path.read_text())
        variant = path.relative_to(args.input).parts[0]
        reason = None
        if metadata.get("grid_size") != 1001:
            reason = "Different grid size"
        elif variant.startswith("perf-"):
            reason = "Profiling instrumentation"
        elif variant.startswith("timing-"):
            reason = "Phase-timing instrumentation"
        elif variant.startswith(("validation-", "final-validation")):
            reason = "Validation run"
        elif variant not in versions:
            reason = "Outside the recorded experiment set"
        elif metadata.get("status") != "completed" or metadata.get("exit_code") != 0:
            reason = "Incomplete or failed trial"
        if reason:
            excluded.append({"source_record": str(path.relative_to(ROOT)), "reason": reason,
                             "grid_size": metadata.get("grid_size", ""),
                             "wall_seconds": metadata.get("wall_seconds", "")})
            continue
        image = (path.parent / "identity.png").read_bytes()
        if image != reference or metadata.get("png_sha256") != digest(image):
            raise RuntimeError(f"PNG verification failed: {path}")
        threads = int(metadata.get("openmp_environment", {}).get("OMP_NUM_THREADS") or 1)
        row = {"variant": variant, "threads": threads, "run": path.parent.name,
               "grid_size": 1001, "wall_seconds": metadata["wall_seconds"],
               "png_matches_reference": True, "png_sha256": digest(image),
               "source_record": str(path.relative_to(ROOT)), "metadata_sha256": digest(path.read_bytes()),
               "compiler_recorded": metadata.get("compiler", ""),
               "build_flags_recorded": metadata.get("build_flags", ""),
               "source_sha256_recorded": metadata.get("source_sha256", ""),
               "binary_sha256_recorded": metadata.get("binary_sha256", "")}
        rows.append(row)
        records.append({"source_record": row["source_record"], "metadata": metadata,
                        "png_byte_identical_to_reference": True})
    if not rows:
        raise RuntimeError("No eligible ordinary trials found")
    order = {entry[0]: i for i, entry in enumerate(VERSIONS)}
    rows.sort(key=lambda row: (order[row["variant"]], row["threads"], row["run"]))
    grouped = {}
    for row in rows:
        grouped.setdefault((row["variant"], row["threads"]), []).append(row["wall_seconds"])
    baseline = statistics.mean(grouped[("original", 1)])
    summaries = []
    for (variant, threads), times in grouped.items():
        _, label, branch, parent, parent_threads, target = versions[variant]
        parent_mean = statistics.mean(grouped[(parent, parent_threads)]) if parent else None
        mean = statistics.mean(times)
        summaries.append({"variant": variant, "label": label, "branch": branch,
                          "threads": threads, "runs": len(times), "mean_seconds": mean,
                          "min_seconds": min(times), "max_seconds": max(times),
                          "sample_stddev_seconds": statistics.stdev(times) if len(times) > 1 else "",
                          "speedup_vs_original_single_run": baseline / mean,
                          "parent_variant": parent or "", "parent_threads": parent_threads or "",
                          "runtime_reduction_vs_parent_percent": 100 * (1 - mean / parent_mean) if parent else "",
                          "make_target": target, "selected_final": variant == "red-black-fused-simd"})
    write_csv(output / "measurements.csv", rows)
    write_csv(output / "summary.csv", summaries)
    # Full-grid and packaging checks use execution records rather than metrics.json.
    for pattern, reason in [("final-validation*/grid/*/execution.json", "Full-grid dump validation"),
                            ("validation-reproduction/status.json", "Packaging validation")]:
        for path in sorted(args.input.glob(pattern)):
            value = json.loads(path.read_text())
            if "elapsed_seconds" in value:
                excluded.append({"source_record": str(path.relative_to(ROOT)), "reason": reason,
                                 "grid_size": 1001, "wall_seconds": value["elapsed_seconds"]})
            else:
                for check in value.get("checks", []):
                    if check["command"][:2] == ["./sandpile.exe", "1001"]:
                        excluded.append({"source_record": str(path.relative_to(ROOT)), "reason": reason,
                                         "grid_size": 1001, "wall_seconds": check["elapsed_seconds"]})
    write_csv(output / "excluded-runs.csv", excluded)
    (output / "measurement-records.json").write_text(json.dumps(records, indent=2) + "\n")
    manifest = {"grid_size": 1001, "time_unit": "seconds", "measurement_count": len(rows),
                "configuration_count": len(summaries), "reference_png_sha256": digest(reference),
                "baseline_samples": len(grouped[("original", 1)]),
                "method": "Arithmetic means of ordinary complete process wall times, including PNG output. "
                          "No separately excluded warm-up; no instrumentation or validation times.",
                "error_bars": "Observed minimum to maximum; individual runs are plotted. No confidence intervals.",
                "missing_metadata": "Blank fields retain missing values from early records; values are not reconstructed.",
                "limitations": ["Original baseline has one ordinary sample.",
                                "Most configurations have only two samples; core-loop has three.",
                                "VM host load and scheduling were not controlled or randomized.",
                                "SIMD/native candidates combine a SIMD directive with native CPU flags."]}
    (output / "methodology.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validation = ROOT / "results/final-validation-03/validation-summary.json"
    if validation.exists():
        (output / "validation-summary.json").write_bytes(validation.read_bytes())
        memory = validation.parent / "memory-summary.json"
        (output / "memory-summary.json").write_bytes(memory.read_bytes())
    vectorization = {}
    for variant in ["red-black-openmp-symmetry-simd", "red-black-fused-simd"]:
        path = args.input / variant / "vectorization-summary.json"
        if path.exists():
            vectorization[variant] = {"source_record": str(path.relative_to(ROOT)),
                                      "compiler_evidence": json.loads(path.read_text())}
    (output / "vectorization.json").write_text(json.dumps(vectorization, indent=2) + "\n")
    profiles = {"measurement_type": "Instrumented evidence; excluded from ordinary timing averages",
                "interpretation": "cycles:u sample percentages describe sampled CPU cycles, not wall-clock fractions",
                "reports": {}}
    for name, relative in [("original", "perf-original/n1001/run-01"),
                           ("A_symmetry_4_threads", "perf-fastest/threads-4/n1001/run-01")]:
        base = args.input / relative
        report = base / "report.txt"
        if not report.exists():
            continue
        text = report.read_text()
        hotspots = []
        for line in text.splitlines():
            match = re.match(r"\s*(\d+\.\d+)%\s+\S+\s+(\S+)\s+\[[^]]+\]\s+(.+)$", line)
            if match:
                hotspots.append({"sample_percent": float(match[1]), "shared_object": match[2], "symbol": match[3]})
        metrics = json.loads((base / "metrics.json").read_text())
        profiles["reports"][name] = {"source_report": str(report.relative_to(ROOT)),
                                    "event": "cycles:u", "lost_samples": 0 if "Total Lost Samples: 0" in text else None,
                                    "instrumented_wall_seconds": metrics["wall_seconds"], "hotspots": hotspots}
    phase_log = args.input / "timing-original/n1001/run-01/stderr.log"
    if phase_log.exists():
        profiles["original_phase_times_seconds"] = {key: float(value) for key, value in
            (line.split("=", 1) for line in phase_log.read_text().splitlines() if "=" in line)}
    (output / "profiling.json").write_text(json.dumps(profiles, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
