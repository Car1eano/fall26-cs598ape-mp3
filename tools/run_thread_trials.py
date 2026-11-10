"""Run an OpenMP variant's trials sequentially after an active trial or comparison."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--after-comparison", type=Path)
    parser.add_argument("--variant", choices=["row-three-color", "red-black-openmp"],
                        default="row-three-color")
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    base = ROOT / "results" / args.variant
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "comparison-status.json"
    state = {"status": "queued", "threads": [1, 2, 4], "results": []}

    def save():
        state_path.write_text(json.dumps(state, indent=2) + "\n")

    save()
    previous_path = args.after_comparison or args.after
    if previous_path:
        state["waiting_for"] = str(previous_path)
        save()
        print(f"Waiting for {previous_path} before timing trials.", flush=True)
        deadline = time.monotonic() + 1800
        while True:
            previous = json.loads(previous_path.read_text())
            if previous["status"] == "completed":
                break
            if previous["status"] not in ["running", "queued", "preparing"]:
                state.update(status="failed", reason="Preceding experiment did not complete successfully")
                save()
                raise SystemExit(1)
            if time.monotonic() >= deadline:
                state.update(status="failed", reason="Preceding experiment did not finish within 30 minutes")
                save()
                raise SystemExit(1)
            time.sleep(5)
    source = ROOT / "variants" / (args.variant + ".c")
    binary = ROOT / ("sandpile-" + args.variant + ".exe")
    if args.prepare:
        state.update(status="preparing")
        save()
        with (base / "build.log").open("w") as log:
            build = subprocess.run(["make", args.variant], cwd=ROOT, stdout=log, stderr=log)
        if build.returncode:
            state.update(status="failed", reason="Build failed")
            save()
            raise SystemExit(1)
        with (base / "grid-check.log").open("w") as log:
            check = subprocess.run([sys.executable, str(ROOT / "tools/check_grid.py"),
                                    "--source", str(source), "--openmp", "--threads", "1", "2", "4",
                                    "--repetitions", "2", "--output", str(base / "grid-check.json")],
                                   cwd=ROOT, stdout=log, stderr=log)
        if check.returncode:
            state.update(status="failed", reason="Grid correctness check failed")
            save()
            raise SystemExit(1)
    (base / "sandpile-source.c").write_bytes(source.read_bytes())
    (base / "Makefile.snapshot").write_bytes((ROOT / "Makefile").read_bytes())
    for threads in [1, 2, 4]:
        state.update(status="running", active_threads=threads)
        save()
        out = base / f"threads-{threads}/n1001/run-01"
        command = [sys.executable, str(ROOT / "tools/run_trial.py"),
                   "--binary", str(binary),
                   "--source", str(source),
                   "--size", "1001", "--threads", str(threads),
                   "--build-flags=-O3 -lm -g -Werror -fopenmp", "--output", str(out)]
        result = subprocess.run(command, cwd=ROOT)
        metrics = json.loads((out / "metrics.json").read_text())
        state["results"].append({"threads": threads, "metrics_path": str(out / "metrics.json"),
                                 "wall_seconds": metrics.get("wall_seconds"),
                                 "matches_reference_png": metrics.get("matches_reference_png")})
        if result.returncode or not metrics.get("matches_reference_png"):
            state.update(status="failed", reason="Trial failed or output did not match reference")
            save()
            raise SystemExit(1)
        save()
    state.update(status="completed", active_threads=None)
    save()
    print(json.dumps(state, indent=2), flush=True)


if __name__ == "__main__":
    main()
