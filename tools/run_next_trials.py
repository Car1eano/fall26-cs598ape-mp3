"""Validate and benchmark symmetry variants, then a SIMD-capable candidate."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 31, 32, 33,
         63, 64, 65, 101, 102, 201]
STATE = ROOT / "results/next-trials/status.json"


def main():
    state = {"status": "running", "stage": "starting", "results": []}
    STATE.parent.mkdir(parents=True, exist_ok=True)

    def save(stage):
        state["stage"] = stage
        STATE.write_text(json.dumps(state, indent=2) + "\n")
        print(stage, flush=True)

    def logged(command, path, env=None):
        with path.open("w") as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=log, check=True)

    def validate(variant, native=False):
        base = ROOT / "results" / variant
        base.mkdir(parents=True, exist_ok=True)
        source = ROOT / "variants" / (variant + ".c")
        binary = ROOT / ("sandpile-" + variant + ".exe")
        flags = "-O3 -lm -g -Werror -fopenmp" + (" -march=native" if native else "")
        save("validating " + variant)
        command = ["gcc", str(source), "-I", str(ROOT), "-o", str(binary)] + flags.split()
        if native:
            command.append("-fopt-info-vec-all=" + str(base / "vectorization.txt"))
        logged(command, base / "build.log")
        command = [sys.executable, "tools/check_grid.py", "--source", str(source), "--openmp",
                   "--threads"] + (["4"] if native else ["1", "2", "4"])
        command += ["--repetitions", "2", "--sizes"] + list(map(str, SIZES))
        command += ["--output", str(base / "grid-check.json")]
        if native:
            command.append("--native")
        logged(command, base / "grid-check.log")
        if not native:
            for size in [31, 32]:
                out = base / "valgrind" / f"n{size}"
                out.mkdir(parents=True, exist_ok=False)
                with (out / "stdout.log").open("w") as stdout, (out / "stderr.log").open("w") as stderr:
                    subprocess.run(["valgrind", "--leak-check=full", "--error-exitcode=1",
                                    str(binary), str(size)], cwd=out,
                                   env=dict(os.environ, OMP_NUM_THREADS="1", OMP_DYNAMIC="FALSE"),
                                   stdout=stdout, stderr=stderr, check=True)
        (base / "sandpile-source.c").write_bytes(source.read_bytes())
        (base / "Makefile.snapshot").write_bytes((ROOT / "Makefile").read_bytes())
        if native:
            lines = source.read_text().splitlines()
            start = next(i for i, line in enumerate(lines, 1) if line.startswith("static void stabilize"))
            end = next(i for i, line in enumerate(lines, 1) if line.startswith("void find_identity"))
            report = (base / "vectorization.txt").read_text()
            hot = []
            for line in report.splitlines():
                location = re.search(r"\.c:(\d+):", line)
                if location and start <= int(location[1]) < end and "optimized: loop vectorized" in line:
                    hot.append(line)
            (base / "vectorization-summary.json").write_text(json.dumps({
                "stabilize_has_vectorized_loops": bool(hot), "hot_loop_messages": hot,
                "flags": flags}, indent=2) + "\n")
            if not hot:
                raise RuntimeError("SIMD candidate did not vectorize stabilize loops; inspect report before timing")
        return source, binary, flags

    def measure(variant, source, binary, flags):
        times = []
        for trial in [1, 2]:
            save(f"timing {variant} run-{trial:02d}")
            out = ROOT / "results" / variant / f"threads-4/n1001/run-{trial:02d}"
            subprocess.run([sys.executable, "tools/run_trial.py", "--binary", str(binary),
                            "--source", str(source), "--size", "1001", "--threads", "4",
                            "--build-flags=" + flags, "--output", str(out)], cwd=ROOT, check=True)
            metrics = json.loads((out / "metrics.json").read_text())
            if not metrics.get("matches_reference_png"):
                raise RuntimeError(f"Reference mismatch: {out}")
            assert (out / "identity.png").read_bytes() == (ROOT / "identity-ref.png").read_bytes()
            (out / "reference-comparison.json").write_text(json.dumps({
                "reference": "identity-ref.png", "files_byte_identical": True}, indent=2) + "\n")
            times.append(metrics["wall_seconds"])
        state["results"].append({"variant": variant, "threads": 4, "times_seconds": times,
                                 "mean_seconds": sum(times) / len(times)})
        save("completed " + variant)

    try:
        variant = "row-three-color-symmetry"
        base = ROOT / "results" / variant
        assert (base / "sandpile-source.c").read_bytes() == (ROOT / "variants" / (variant + ".c")).read_bytes()
        assert all(r["all_cells_equal"] for r in json.loads((base / "grid-check.json").read_text()))
        measure(variant, ROOT / "variants" / (variant + ".c"),
                ROOT / ("sandpile-" + variant + ".exe"), "-O3 -lm -g -Werror -fopenmp")
        variant = "red-black-openmp-symmetry"
        measure(variant, *validate(variant))
        # The row-three-color kernel has a horizontal in-place dependence.
        # Red-black gather loops permit SIMD without changing their semantics.
        variant = "red-black-openmp-symmetry-simd"
        measure(variant, *validate(variant, native=True))
        state["status"] = "completed"
        state["selected_variant"] = min(state["results"], key=lambda r: r["mean_seconds"])["variant"]
        save("all trials completed")
    except Exception as error:
        state.update(status="failed", error=str(error))
        save("stopped; inspection required")
        raise


if __name__ == "__main__":
    main()
