#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

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
static int *grid_storage;
static size_t grid_stride;
static int *row_begin;
static int *row_end;

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
  do {
    changed = 0;
    for (int i = 0; i < N; ++i) {
      for (int j = row_begin[i]; j <= row_end[i]; ++j) {
        int *cell = grid[i] + j;
        if (*cell < 4)
          continue;
        changed = 1; // topple it
#ifdef SINGLE_TOPPLE
        int topples = 1;
#else
        int topples = *cell / 4;
#endif
        *cell -= 4 * topples;
        *(cell - grid_stride) += topples;
        cell[-1] += topples;
        *(cell + grid_stride) += topples;
        cell[1] += topples;
      }
    }
  } while (changed);
}

void find_identity() {
  prepare_row_bounds();
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < N; ++j) {
      grid[i][j] = 6;
    }
  }
  stabilize();
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < N; ++j) {
      grid[i][j] = 6 - grid[i][j];
    }
  }
  stabilize();
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

  grid_stride = (size_t)N + 2;
  if (grid_stride > SIZE_MAX / grid_stride / sizeof(*grid_storage))
    die("grid size exceeds allocation limit");
  grid_storage = calloc(grid_stride * grid_stride, sizeof(*grid_storage));
  grid = malloc((size_t)N * sizeof(*grid));
  if (!grid_storage || !grid)
    die("malloc failed for grid");
  for (int i = 0; i < N; ++i) {
    grid[i] = grid_storage + ((size_t)i + 1) * grid_stride + 1;
  }

  find_identity();

  render("identity.png");
  free(row_begin);
  free(row_end);
  free(grid_storage);
  free(grid);
  return EXIT_SUCCESS;
}
