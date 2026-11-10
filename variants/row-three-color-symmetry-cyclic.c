#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <omp.h>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#define MAX(a, b) (((a) > (b)) ? (a) : (b))

static void die(const char *s) {
  fprintf(stderr, "%s\n", s);
  exit(1);
}

int N = 801;
int **grid;
static int *row_begin;
static int *row_end;
static int work_rows;
static int use_reflection;

static void prepare_row_bounds(void) {
  row_begin = malloc((size_t)N * sizeof(*row_begin));
  row_end = malloc((size_t)N * sizeof(*row_end));
  if (!row_begin || !row_end)
    die("malloc failed for row bounds");
  int64_t radius = N / 2;
  for (int i = 0; i < N; ++i) {
    row_begin[i] = N;
    row_end[i] = -1;
    int64_t dy = i - radius;
    for (int j = 0; j <= MAX(i, N - 1 - i); ++j) {
      int64_t dx = j - radius;
      if (dy * dy + dx * dx <= radius * radius) {
        if (row_begin[i] == N)
          row_begin[i] = j;
        row_end[i] = j;
      }
    }
  }
}

// you can also use this function to debug print your sandpile
static void render(char *filename) {
  int chan = 3;
  unsigned char *pixels = (unsigned char *)malloc(N * N * chan * sizeof(char));
  int stride = N * chan;
  if (!pixels)
    die("malloc failed for PNG pixel buffer");
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < N; ++j) {
      unsigned char r = 0, g = 0, b = 0;
      switch (grid[i][j]) {
      case 0: // obsidian
        r = 15;
        g = 15;
        b = 25;
        break;
      case 1: // electric cyan
        r = 0;
        g = 210;
        b = 255;
        break;
      case 2: // vibrant magenta
        r = 230;
        g = 30;
        b = 130;
        break;
      case 3: // bright gold
        r = 255;
        g = 200;
        b = 0;
        break;
      default: // white
        r = 0;
        g = 0;
        b = 0;
      }

      int pid = (i * N + j) * chan;
      pixels[pid] = r;
      pixels[pid + 1] = g;
      pixels[pid + 2] = b;
    }
  }
  if (stbi_write_png(filename, N, N, chan, pixels, stride)) {
    printf("Successfully saved sandpile identity to: %s\n", filename);
  } else {
    die("Error: stb_image_write failed to save png file\n");
  }
  free(pixels);
}

static void stabilize() {
  int changed = 0;
#pragma omp parallel shared(changed)
  {
    int repeat;
#pragma omp single
    fprintf(stderr, "openmp_threads=%d\n", omp_get_num_threads());
    do {
#pragma omp single
      changed = 0;
      for (int group = 0; group < 3; ++group) {
        // Source rows are three apart, so their touched row ranges do not overlap.
        // Each source row is processed sequentially by its assigned thread.
#pragma omp for schedule(static, 1) reduction(|:changed)
        for (int i = group; i < work_rows; i += 3) {
          // The mirrored pair next to the middle sends two contributions
          // to the single middle row. Other representative rows receive one.
          int down_weight = use_reflection && i + 1 == work_rows - 1 ? 2 : 1;
          for (int j = row_begin[i]; j <= row_end[i]; ++j) {
            int value = grid[i][j];
            if (value < 4)
              continue;
            int topples = value / 4;
            changed = 1;
            grid[i][j] -= 4 * topples;
            if (i > 0)
              grid[i - 1][j] += topples;
            if (j > 0)
              grid[i][j - 1] += topples;
            if (i + 1 < work_rows)
              grid[i + 1][j] += down_weight * topples;
            if (j < N - 1)
              grid[i][j + 1] += topples;
          }
        }
        // The implicit worksharing barrier separates consecutive row groups.
      }
      // Copy the decision to private variables before the next shared reset.
#pragma omp single copyprivate(repeat)
      repeat = changed;
    } while (repeat);
  }
}

void find_identity() {
  // The original integer-centered mask is reflection-symmetric only for odd N.
  use_reflection = N % 2 != 0;
  work_rows = use_reflection ? N / 2 + 1 : N;
  prepare_row_bounds();
  for (int i = 0; i < work_rows; ++i) {
    for (int j = 0; j < N; ++j) {
      grid[i][j] = 6;
    }
  }
  stabilize();
  for (int i = 0; i < work_rows; ++i) {
    for (int j = 0; j < N; ++j) {
      grid[i][j] = 6 - grid[i][j];
    }
  }
  stabilize();
  if (use_reflection) {
    for (int i = 0; i < N / 2; ++i)
      memcpy(grid[N - 1 - i], grid[i], (size_t)N * sizeof(int));
  }
}

int main(int argc, char **argv) {
  if (argc < 2 || argc > 2) {
    fprintf(stderr, "Usage: %s N\n", argv[0]);
    return EXIT_FAILURE;
  }
  char *end;
  uintmax_t parsed = strtoumax(argv[1], &end, 10);
  if (errno || argv[1][0] < '0' || argv[1][0] > '9' || *end || !parsed ||
      parsed > INT32_MAX)
    die("grid size must be a positive int");
  N = (int)parsed;

  grid = (int **)malloc(N * sizeof(int *));
  for (int i = 0; i < N; ++i) {
    grid[i] = (int *)malloc(N * sizeof(int));
  }

  find_identity();

  render("identity.png");
  free(row_begin);
  free(row_end);
  for (int i = 0; i < N; ++i) {
    free(grid[i]);
  }
  free(grid);
  return EXIT_SUCCESS;
}
