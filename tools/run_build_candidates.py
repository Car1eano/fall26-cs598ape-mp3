"""Validate and time the fused SIMD and core-loop LTO build candidates."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 31, 32, 33,
         63, 64, 65, 101, 102, 201]


def main():
    root = ROOT / "results/build-candidates"
    root.mkdir(parents=True, exist_ok=True)
    state = {"status": "running", "stage": "starting", "results": []}

    def save(stage):
        state["stage"] = stage
        (root / "status.json").write_text(json.dumps(state, indent=2) + "\n")
        print(stage, flush=True)

    try:
        for variant, source_name, extra in [
            ("red-black-fused-simd", "red-black-fused-simd", ["-march=native"]),
            ("row-three-color-core-loop-lto", "row-three-color-core-loop", ["-flto"]),
        ]:
            base = ROOT / "results" / variant
            base.mkdir(parents=True, exist_ok=True)
            source = ROOT / "variants" / (source_name + ".c")
            binary = ROOT / ("sandpile-" + variant + ".exe")
            flags = ["-O3", "-lm", "-g", "-Werror", "-fopenmp"] + extra
            command = ["gcc", str(source), "-I", str(ROOT), "-o", str(binary)] + flags
            native = "-march=native" in extra
            if native:
                command.append("-fopt-info-vec-all=" + str(base / "vectorization.txt"))
            save("building " + variant)
            with (base / "build.log").open("w") as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)
            save("validating " + variant)
            command = [sys.executable, "tools/check_grid.py", "--source", str(source), "--openmp",
                       "--threads", "4", "--repetitions", "2", "--sizes"] + list(map(str, SIZES))
            command += ["--output", str(base / "grid-check.json"), "--native" if native else "--lto"]
            with (base / "grid-check.log").open("w") as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)
            (base / "sandpile-source.c").write_bytes(source.read_bytes())
            (base / "Makefile.snapshot").write_bytes((ROOT / "Makefile").read_bytes())
            if native:
                lines = source.read_text().splitlines()
                begin = next(i for i, line in enumerate(lines, 1) if line.startswith("static void stabilize"))
                end = next(i for i, line in enumerate(lines, 1) if line.startswith("void find_identity"))
                hot = []
                for line in (base / "vectorization.txt").read_text().splitlines():
                    match = re.search(r"\.c:(\d+):", line)
                    if match and begin <= int(match[1]) < end and "optimized: loop vectorized" in line:
                        hot.append(line)
                (base / "vectorization-summary.json").write_text(json.dumps({
                    "stabilize_has_vectorized_loops": bool(hot), "messages": hot}, indent=2) + "\n")
                if not hot:
                    raise RuntimeError("The fused SIMD candidate did not vectorize its core loop")
            times = []
            for run in [1, 2]:
                save(f"timing {variant} run-{run:02d}")
                out = base / f"threads-4/n1001/run-{run:02d}"
                subprocess.run([sys.executable, "tools/run_trial.py", "--binary", str(binary),
                                "--source", str(source), "--size", "1001", "--threads", "4",
                                "--build-flags=" + " ".join(flags), "--output", str(out)],
                               cwd=ROOT, check=True)
                metrics = json.loads((out / "metrics.json").read_text())
                if not metrics.get("matches_reference_png"):
                    raise RuntimeError(f"Reference mismatch: {out}")
                assert (out / "identity.png").read_bytes() == (ROOT / "identity-ref.png").read_bytes()
                (out / "reference-comparison.json").write_text(json.dumps({
                    "reference": "identity-ref.png", "files_byte_identical": True}, indent=2) + "\n")
                times.append(metrics["wall_seconds"])
            state["results"].append({"variant": variant, "times_seconds": times,
                                     "mean_seconds": sum(times) / len(times)})
            save("completed " + variant)
        state["status"] = "completed"
        save("all candidates completed")
    except Exception as error:
        state.update(status="failed", error=str(error))
        save("stopped; inspection required")
        raise


if __name__ == "__main__":
    main()
