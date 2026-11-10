# Experiment reproduction

Run commands from the repository root. Each target builds independently; earlier
versions do not need to run before the final version.

## Environment

Measurements used the Ubuntu 26.04.1 course VM: four virtual CPUs, Intel Xeon Silver
4216 at 2.10 GHz, about 15 GiB RAM, GCC 15.2.0, GNU Make 4.4.1, and Python 3.14.4.
All variants use `-O3 -lm -g -Werror`. OpenMP variants add `-fopenmp`; SIMD/native
variants also add `-march=native`. The LTO candidate instead adds `-flto`.
The `row-bounds` target uses `-DSINGLE_TOPPLE` to disable batch toppling.

OpenMP measurements fix `OMP_NUM_THREADS=4`, `OMP_DYNAMIC=FALSE`,
`OMP_PROC_BIND=close`, and `OMP_PLACES=cores`, except the explicit 1/2/4-thread
comparisons. Run benchmarks sequentially on an otherwise idle VM. No warm-up run
is excluded: every requested run is recorded. Timing covers the complete process,
including PNG output, and excludes compilation and instrumentation.

## Versions

For named targets, `make NAME` builds `sandpile-NAME.exe`. `make` builds the selected
final source, `sandpile.c`, as `sandpile.exe`. The preserved final snapshot is
`variants/red-black-fused-simd.c`; the untouched original is `baseline/sandpile.c`.
Other sources are `variants/NAME.c`, with the exceptions noted below.

| Target / experiment name | Change and parent |
| --- | --- |
| `baseline` | Original implementation |
| `row-bounds` | Baseline + precomputed row bounds; source `row-bounds-batch.c` |
| `batch-toppling` | Row bounds + batch toppling; source `row-bounds-batch.c` |
| `flat-padding` | Batch toppling + contiguous storage and halo padding |
| `two-phase` | Flat padding + separate toppling and gathering passes |
| `red-black` | Two-phase + checkerboard order and smaller receiving ranges |
| `row-three-color` | Branch A: batch toppling + three row groups and OpenMP |
| `red-black-openmp` | Branch B: red-black + OpenMP |
| `row-three-color-symmetry` | A + reflection symmetry |
| `red-black-openmp-symmetry` | B + reflection symmetry |
| `red-black-openmp-symmetry-simd` | B symmetry + SIMD/native |
| `row-three-color-symmetry-cyclic` | A symmetry + cyclic row scheduling |
| `row-three-color-local-flags` | A cyclic + per-thread termination flags |
| `row-three-color-core-loop` | A cyclic + simpler interior loop and cached pointers |
| `row-three-color-core-loop-lto` | Core loop + LTO; source `row-three-color-core-loop.c` |
| `red-black-fused` | B symmetry + fused gathering and toppling |
| `red-black-fused-simd` | Fused red-black + SIMD/native; selected final algorithm |
| `all` / `final` | Default build / experiment name for the selected final version |

Symmetry variants simulate the upper half for odd sizes, handle center-row
contributions, and reconstruct the full grid. Even sizes use the full grid.
All versions preserve the values of interior cells outside the active shape.

## Timed runs

Run the final version twice with saved outputs:

```bash
python3 tools/reproduce.py --variant final --runs 2 --output results/reproduce-final
```

The default size is 1001 and the default OpenMP team size is four. Each trial saves
its PNG, elapsed time, compiler flags, source snapshot, executable hash, and logs.
At size 1001, a PNG mismatch fails the experiment. `summary.csv` contains the mean,
minimum, maximum, and sample standard deviation. Output directories must be new.

Select experiment names from the table in the desired execution order; use
`final` for the default `all` build target:

```bash
python3 tools/reproduce.py --variant baseline row-bounds batch-toppling final --runs 2 --output results/reproduce-stages
```

The baseline takes about ten minutes per run. For quick execution checks, use
`--size 31 --runs 1`. To reproduce thread scaling, repeat a parallel variant with
`--threads 1`, `--threads 2`, and `--threads 4`, using a different output directory
for each command. Serial variants always use one thread.

The selected version originally took 25.088 and 25.236 seconds (mean 25.162) at
1001 × 1001. The original ordinary run took 616.234 seconds, a single sample;
the resulting 24.49× speedup is relative to that sample. VM scheduling and host
load can change timings. The SIMD/native comparison combines both changes.

## Correctness and memory checks

The README command checks the final PNG. For a quick numerical comparison,
including cells whose different values can share a PNG color:

```bash
python3 tools/check_grid.py --source sandpile.c --openmp --native --threads 4 --repetitions 2 --output results/check-final.json
```

Use a named variant's source and omit `--openmp` or `--native` when those build
options do not apply; use `--lto` for the LTO candidate. Row-bounds and batch-toppling
share their final stable grid, so the default batch source suffices for that check.

Optional full-grid and memory validation requires Valgrind:

```bash
sudo apt-get install valgrind
make
python3 tools/validate_final.py --output results/validate-final
```

This additional validation reruns the original once and the final version twice
at size 1001, comparing all 1,002,001 integers. It also runs small Memcheck and
ASan/UBSan cases; its timings are excluded from benchmarks. Valgrind uses the same
source with AVX-512 disabled because the installed Valgrind could not decode an
instruction in the native executable. ASan/UBSan retains native compilation.
OpenMP's thread TLS allocations can appear as possibly lost or still reachable;
inspect the saved XML. LeakSanitizer needs an execution environment without
incompatible process tracing.

## Optional profiling

Install the optional profiling tool if needed, then record the final executable
separately:

```bash
sudo apt-get install linux-perf
make
mkdir -p results/profile-final
cd results/profile-final
OMP_NUM_THREADS=4 OMP_DYNAMIC=FALSE OMP_PROC_BIND=close OMP_PLACES=cores perf record -e cycles:u -g -o perf.data -- ../../sandpile.exe 1001
perf report --stdio -i perf.data > report.txt
```

Profiling used `perf` 7.0.14. The VM initially blocked sampling with
`kernel.perf_event_paranoid=4`; temporarily setting it to `2` allowed user-space
events. This permission change is needed only for profiling, not normal execution.
Memcheck used Valgrind 3.26.0.
