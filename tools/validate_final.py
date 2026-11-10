"""Preserve full-grid comparisons and Memcheck evidence for the selected version."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/final-validation")
    parser.add_argument("--source", type=Path, default=ROOT / "sandpile.c")
    parser.add_argument("--binary", type=Path, default=ROOT / "sandpile.exe")
    parser.add_argument("--reference-metrics", type=Path,
                        help="Optionally require exact source and binary hashes from a previous trial")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "running", "stage": "preparing", "checks": []}

    def save(stage):
        state.update(stage=stage, updated_utc=datetime.now(timezone.utc).isoformat())
        (output / "status.json").write_text(json.dumps(state, indent=2) + "\n")
        print(stage, flush=True)

    def run(command, directory, threads=1, stdout="stdout.log"):
        env = dict(os.environ, OMP_NUM_THREADS=str(threads), OMP_DYNAMIC="FALSE",
                   OMP_PROC_BIND="close", OMP_PLACES="cores")
        record = {"command": list(map(str, command)), "threads": threads,
                  "started_utc": datetime.now(timezone.utc).isoformat(),
                  "purpose": "correctness or memory validation; not a benchmark"}
        (directory / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
        start = time.perf_counter()
        with (directory / stdout).open("wb") as out, (directory / "stderr.log").open("wb") as err:
            result = subprocess.run(command, cwd=directory, env=env, stdout=out, stderr=err)
        record.update(exit_code=result.returncode, elapsed_seconds=time.perf_counter() - start)
        (directory / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(f"Validation command failed: {directory}")

    try:
        save("saving selected sources and binary")
        sources = {"baseline": ROOT / "baseline/sandpile.c",
                   "optimized": args.source.resolve()}
        selected = args.binary.resolve()
        if args.reference_metrics:
            measured = json.loads(args.reference_metrics.read_text())
            if sha256(selected) != measured["binary_sha256"] or sha256(sources["optimized"]) != measured["source_sha256"]:
                raise RuntimeError("Selected source or executable differs from the measured version")
        snapshot_binary = output / selected.name
        shutil.copy2(selected, snapshot_binary)
        metadata = {"compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
                    "valgrind": subprocess.check_output(["valgrind", "--version"], text=True).strip(),
                    "selected_binary_sha256": sha256(selected), "sources": {}}
        binaries = {}
        marker = '  render("identity.png");'
        replacement = '''  for (int row = 0; row < N; ++row) {
    if (fwrite(grid[row], sizeof(int), N, stdout) != (size_t)N)
      die("grid dump failed");
  }'''
        for name, source in sources.items():
            text = source.read_text()
            if text.count(marker) != 1:
                raise RuntimeError(f"Unexpected rendering call: {source}")
            (output / f"{name}-source.c").write_text(text)
            generated = output / f"{name}-grid.c"
            generated.write_text(text.replace(marker, replacement))
            binary = output / f"{name}-grid.exe"
            flags = ["-O3", "-lm", "-g", "-Werror"]
            if name == "optimized":
                flags += ["-fopenmp", "-march=native"]
            command = ["gcc", str(generated), "-I", str(ROOT), "-o", str(binary)] + flags
            subprocess.run(command, stdout=subprocess.DEVNULL, check=True)
            metadata["sources"][name] = {"path": str(source), "sha256": sha256(source),
                                          "dump_binary_sha256": sha256(binary), "build_command": command}
            binaries[name] = binary
        compatibility_binary = output / "optimized-memcheck.exe"
        compatibility_command = ["gcc", str(sources["optimized"]), "-I", str(ROOT),
                                 "-o", str(compatibility_binary), "-O3", "-lm", "-g", "-Werror",
                                 "-fopenmp", "-march=native", "-mno-avx512f"]
        sanitizer_binary = output / "optimized-sanitizers.exe"
        sanitizer_command = ["gcc", str(sources["optimized"]), "-I", str(ROOT),
                             "-o", str(sanitizer_binary), "-O2", "-lm", "-g", "-Werror",
                             "-fopenmp", "-march=native", "-fno-omit-frame-pointer",
                             "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
        for command in [compatibility_command, sanitizer_command]:
            subprocess.run(command, stdout=subprocess.DEVNULL, check=True)
        metadata["memory_validation"] = {
            "memcheck_build_command": compatibility_command,
            "sanitizer_build_command": sanitizer_command,
            "limitation": "Native executable uses an AVX-512 instruction unsupported by this Valgrind. "
                          "Memcheck uses the same source with AVX-512 disabled; sanitizer build retains native flags. "
                          "Neither instrumented run is a benchmark."}
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

        for size in [1, 2, 31, 32]:
            for threads in [1, 4]:
                save(f"Memcheck N={size}, threads={threads}")
                directory = output / f"memcheck/n{size}/threads-{threads}"
                directory.mkdir(parents=True)
                xml = directory / "memcheck.xml"
                run(["valgrind", "--tool=memcheck", "--leak-check=full", "--show-leak-kinds=all",
                     "--errors-for-leak-kinds=definite,indirect", "--error-exitcode=99",
                     "--xml=yes", "--xml-file=" + str(xml), str(compatibility_binary), str(size)], directory, threads)
                errors = ET.parse(xml).getroot().findall("error")
                kinds = [error.findtext("kind") for error in errors]
                serious = [kind for kind in kinds if kind not in ["Leak_StillReachable", "Leak_PossiblyLost"]]
                if serious:
                    raise RuntimeError(f"Memcheck errors in {directory}: {serious}")
                state["checks"].append({"type": "memcheck", "size": size, "threads": threads,
                                         "invalid_access_or_definite_indirect_leak": False,
                                         "reported_kinds": kinds, "avx512_disabled": True})
                save(f"Memcheck passed N={size}, threads={threads}")

        for size in [1, 2, 31, 32, 101, 102]:
            for threads in [1, 4]:
                save(f"ASan/UBSan N={size}, threads={threads}")
                directory = output / f"sanitizers/n{size}/threads-{threads}"
                directory.mkdir(parents=True)
                run([str(sanitizer_binary), str(size)], directory, threads)
                state["checks"].append({"type": "asan_ubsan", "size": size,
                                         "threads": threads, "exit_code": 0, "native": True})
                save(f"ASan/UBSan passed N={size}, threads={threads}")

        save("running baseline full-grid dump N=1001")
        baseline_dir = output / "grid/baseline"
        baseline_dir.mkdir(parents=True)
        run([str(binaries["baseline"]), "1001"], baseline_dir, stdout="grid.bin")
        reference = (baseline_dir / "grid.bin").read_bytes()
        expected_bytes = 1001 * 1001 * struct.calcsize("i")
        if len(reference) != expected_bytes:
            raise RuntimeError(f"Unexpected baseline dump length: {len(reference)}")
        save("baseline grid complete; comparing selected version")
        for trial in [1, 2]:
            directory = output / f"grid/optimized-run-{trial:02d}"
            directory.mkdir(parents=True)
            save(f"running optimized full-grid dump N=1001, run-{trial:02d}")
            run([str(binaries["optimized"]), "1001"], directory, threads=4, stdout="grid.bin")
            actual = (directory / "grid.bin").read_bytes()
            equal = actual == reference
            record = {"type": "full_grid", "size": 1001, "threads": 4, "run": trial,
                      "all_cells_equal": equal, "compared_cells": 1001 * 1001,
                      "baseline_bytes": len(reference), "optimized_bytes": len(actual),
                      "baseline_sha256": hashlib.sha256(reference).hexdigest(),
                      "optimized_sha256": hashlib.sha256(actual).hexdigest()}
            if (directory / "stderr.log").read_text().splitlines() != ["openmp_threads=4"] * 2:
                raise RuntimeError("Unexpected OpenMP team size in full-grid validation")
            state["checks"].append(record)
            (directory / "comparison.json").write_text(json.dumps(record, indent=2) + "\n")
            if not equal:
                raise RuntimeError(f"Full grid mismatch: {directory}")
            save(f"full-grid comparison passed run-{trial:02d}")
        state["status"] = "completed"
        save("all final correctness and memory checks completed")
    except Exception as error:
        state.update(status="failed", error=str(error))
        save("validation stopped; inspection required")
        raise


if __name__ == "__main__":
    main()
