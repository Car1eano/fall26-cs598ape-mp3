"""Compare small-grid sweep counts and instrumented elapsed times."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = []
    sources = [("batch-toppling", ROOT / "variants/row-bounds-batch.c"),
               ("two-phase", ROOT / "variants/two-phase.c"),
               ("red-black", ROOT / "variants/red-black.c")]
    with tempfile.TemporaryDirectory(prefix="sandpile-sweeps-") as directory:
        directory = Path(directory)
        for name, source in sources:
            text = source.read_text()
            start = text.index("static void stabilize() {")
            end = text.index("\nvoid find_identity()", start)
            function = text[start:end]
            function = function.replace("static void stabilize() {",
                                        "static void stabilize() {\n  unsigned long long sweeps = 0;", 1)
            if "  do {" in function:
                function = function.replace("  do {", "  do {\n    ++sweeps;", 1)
            else:
                function = function.replace("  for (;;) {", "  for (;;) {\n    ++sweeps;", 1)
            close = function.rfind("}")
            function = (function[:close] +
                        '  fprintf(stderr, "sweeps=%llu\\n", sweeps);\n' + function[close:])
            generated = directory / (name + ".c")
            generated.write_text(text[:start] + function + text[end:])
            binary = directory / name
            subprocess.run(["gcc", str(generated), "-I", str(ROOT), "-O3", "-lm",
                            "-g", "-Werror", "-o", str(binary)], check=True)
            for trial in range(1, 3):
                start_time = time.perf_counter()
                run = subprocess.run([str(binary), "201"], cwd=directory,
                                     capture_output=True, text=True, check=True)
                elapsed = time.perf_counter() - start_time
                sweeps = [int(line.split("=")[1]) for line in run.stderr.splitlines()
                          if line.startswith("sweeps=")]
                result = {"variant": name, "grid_size": 201, "run": trial,
                          "wall_seconds": elapsed, "stabilization_sweeps": sweeps}
                results.append(result)
                print(json.dumps(result), flush=True)
    output = ROOT / "results/red-black/small-comparison.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "note": "Instrumented exploratory runs; a red-black sweep includes both colors. "
                "Sweep costs differ across algorithms; these are not formal benchmark times.",
        "results": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
