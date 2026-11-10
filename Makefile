FUNC := gcc
FLAGS := -O3 -lm -g -Werror

.PHONY: all baseline row-bounds batch-toppling flat-padding two-phase red-black row-three-color red-black-openmp row-three-color-symmetry red-black-openmp-symmetry red-black-openmp-symmetry-simd row-three-color-symmetry-cyclic row-three-color-local-flags row-three-color-core-loop red-black-fused red-black-fused-simd row-three-color-core-loop-lto clean

all: sandpile.exe

sandpile.exe: sandpile.c stb_image_write.h Makefile
	$(FUNC) ./sandpile.c -I . -o ./sandpile.exe $(FLAGS) -fopenmp -march=native

baseline:
	$(FUNC) ./baseline/sandpile.c -I . -o ./sandpile-baseline.exe $(FLAGS)

row-bounds:
	$(FUNC) ./variants/row-bounds-batch.c -I . -DSINGLE_TOPPLE -o ./sandpile-row-bounds.exe $(FLAGS)

batch-toppling:
	$(FUNC) ./variants/row-bounds-batch.c -I . -o ./sandpile-batch-toppling.exe $(FLAGS)

flat-padding:
	$(FUNC) ./variants/flat-padding.c -I . -o ./sandpile-flat-padding.exe $(FLAGS)

two-phase:
	$(FUNC) ./variants/two-phase.c -I . -o ./sandpile-two-phase.exe $(FLAGS)

red-black:
	$(FUNC) ./variants/red-black.c -I . -o ./sandpile-red-black.exe $(FLAGS)

row-three-color:
	$(FUNC) ./variants/row-three-color.c -I . -o ./sandpile-row-three-color.exe $(FLAGS) -fopenmp

red-black-openmp:
	$(FUNC) ./variants/red-black-openmp.c -I . -o ./sandpile-red-black-openmp.exe $(FLAGS) -fopenmp

row-three-color-symmetry:
	$(FUNC) ./variants/row-three-color-symmetry.c -I . -o ./sandpile-row-three-color-symmetry.exe $(FLAGS) -fopenmp

red-black-openmp-symmetry:
	$(FUNC) ./variants/red-black-openmp-symmetry.c -I . -o ./sandpile-red-black-openmp-symmetry.exe $(FLAGS) -fopenmp

red-black-openmp-symmetry-simd:
	$(FUNC) ./variants/red-black-openmp-symmetry-simd.c -I . -o ./sandpile-red-black-openmp-symmetry-simd.exe $(FLAGS) -fopenmp -march=native

row-three-color-symmetry-cyclic:
	$(FUNC) ./variants/row-three-color-symmetry-cyclic.c -I . -o ./sandpile-row-three-color-symmetry-cyclic.exe $(FLAGS) -fopenmp

row-three-color-local-flags:
	$(FUNC) ./variants/row-three-color-local-flags.c -I . -o ./sandpile-row-three-color-local-flags.exe $(FLAGS) -fopenmp

row-three-color-core-loop:
	$(FUNC) ./variants/row-three-color-core-loop.c -I . -o ./sandpile-row-three-color-core-loop.exe $(FLAGS) -fopenmp

red-black-fused:
	$(FUNC) ./variants/red-black-fused.c -I . -o ./sandpile-red-black-fused.exe $(FLAGS) -fopenmp

red-black-fused-simd:
	$(FUNC) ./variants/red-black-fused-simd.c -I . -o ./sandpile-red-black-fused-simd.exe $(FLAGS) -fopenmp -march=native

row-three-color-core-loop-lto:
	$(FUNC) ./variants/row-three-color-core-loop.c -I . -o ./sandpile-row-three-color-core-loop-lto.exe $(FLAGS) -fopenmp -flto

clean:
	rm -f ./*.exe
