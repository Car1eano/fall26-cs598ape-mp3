"""Run one trial in a new directory and preserve output and timing metadata."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "sandpile.c")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--build-flags", default="-O3 -lm -g -Werror -fopenmp -march=native")
    args = parser.parse_args()
    binary = args.binary.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    if args.threads is not None:
        environment.update(OMP_NUM_THREADS=str(args.threads), OMP_DYNAMIC="FALSE",
                           OMP_PROC_BIND="close", OMP_PLACES="cores")
    def git_output(*arguments):
        result = subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else None

    metadata = {
        "status": "running", "grid_size": args.size,
        "command": [str(binary), str(args.size)],
        "source_commit": git_output("rev-parse", "HEAD"),
        "git_status": git_output("status", "--short"),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "source_path": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "openmp_environment": {key: environment.get(key) for key in
                               ["OMP_NUM_THREADS", "OMP_DYNAMIC", "OMP_PROC_BIND", "OMP_PLACES"]},
        "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "build_flags": args.build_flags,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output / "source.patch").write_text(git_output("diff", "--", "sandpile.c", "Makefile") or "")
    (output / "source.c").write_bytes(args.source.read_bytes())
    (output / "Makefile.snapshot").write_bytes((ROOT / "Makefile").read_bytes())
    metrics = output / "metrics.json"
    metrics.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Starting N={args.size}: {output}", flush=True)
    start = time.perf_counter()
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        result = subprocess.run(metadata["command"], cwd=output, stdout=stdout, stderr=stderr,
                                env=environment)
    metadata.update(status="completed" if result.returncode == 0 else "failed",
                    exit_code=result.returncode, wall_seconds=time.perf_counter() - start)
    image = output / "identity.png"
    if image.exists():
        data = image.read_bytes()
        metadata["png_sha256"] = hashlib.sha256(data).hexdigest()
        if args.size == 1001:
            metadata["matches_reference_png"] = data == (ROOT / "identity-ref.png").read_bytes()
    metrics.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
