"""Compile temporary grid-dump variants and compare every cell with baseline."""
import json
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = [1, 2, 3, 4, 5, 10, 16, 31, 32, 63, 101]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/grid-check.json")
    parser.add_argument("--source", type=Path, default=ROOT / "sandpile.c")
    parser.add_argument("--openmp", action="store_true")
    parser.add_argument("--threads", nargs="+", type=int, default=[1])
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--sizes", nargs="+", type=int, default=SIZES)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--lto", action="store_true")
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix="sandpile-check-") as temp:
        temp = Path(temp)
        binaries = []
        for name, source in [("baseline", ROOT / "baseline/sandpile.c"),
                             ("optimized", args.source)]:
            text = source.read_text()
            marker = '  render("identity.png");'
            assert text.count(marker) == 1
            text = text.replace(marker, '''  for (int row = 0; row < N; ++row) {
    if (fwrite(grid[row], sizeof(int), N, stdout) != (size_t)N)
      die("grid dump failed");
  }''')
            generated = temp / (name + ".c")
            generated.write_text(text)
            binary = temp / name
            flags = ["-fopenmp"] if args.openmp and name == "optimized" else []
            if args.native and name == "optimized":
                flags.append("-march=native")
            if args.lto and name == "optimized":
                flags.append("-flto")
            subprocess.run(["gcc", str(generated), "-I", str(ROOT), "-O3",
                            "-lm", "-g", "-Werror", "-o", str(binary)] + flags, check=True)
            binaries.append(binary)
        for size in args.sizes:
            reference = subprocess.check_output([str(binaries[0]), str(size)], cwd=temp)
            for threads in args.threads:
                env = dict(os.environ, OMP_NUM_THREADS=str(threads), OMP_DYNAMIC="FALSE")
                for trial in range(1, args.repetitions + 1):
                    result = subprocess.run([str(binaries[1]), str(size)], cwd=temp,
                                            env=env, capture_output=True, check=True)
                    equal = reference == result.stdout
                    results.append({"grid_size": size, "threads": threads,
                                    "run": trial, "all_cells_equal": equal})
                    if not equal:
                        raise RuntimeError(f"Grid mismatch at N={size}, threads={threads}")
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(f"All {len(results)} comparisons across {len(args.sizes)} sizes match baseline cell for cell.")


if __name__ == "__main__":
    main()
