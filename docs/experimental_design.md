# Experimental design

## 1. Purpose

This experiment benchmarks execution time and memory usage for both recursive and iterative versions of the Factorial, Binary tree traversal and merge sort implementations in Python, Rust and Java.

## 2. Programming Languages and runtimes

The three programming languages used are:

| Language | Execution model                |
| -------- | ------------------------------ |
| Python   | CPython                        |
| Java     | OpenJDK/JVM,                   |
| Rust     | rustc, optimised release build |

Both builds of Python, Java and Rust code are created by the benchmarking scripts. Rust builds are created using `cargo build --release`. This information is recorded in the run manifest.

## 3. Algorithms and exact specifications

### Factorial modulo 1000000007

Given a non-negative number `n`, calculate `n! mod 1,000,000,007`. In the recursive version of the algorithm the function recursively multiplies `n` down and applies modulo in every multiplication. In the iterative version the function multiplies the sequence of numbers from `n` down through the loop and applies the modulo at the same step. Both versions return `1` for `0` and `1`.

### Binary tree

The input is a binary tree. Node `i` has left child `2i + 1` and right child `2i + 2`. The required traversal order is:

1. Traverse the left subtree.
2. Traverse the current node.
3. Traverse the right subtree.


### Merge sort

The recursive implementation partitions at `floor(length / 2)`, recursively sorts the left and right halves and then merges them. The iterative implementation uses a stack to stimulate recursion. Divided frames are visited again after their child frames in the same order usage the same midpoint calculation.


## 4. Input datasets

All languages will use the same test datasets from `test_data/`. The generator in `scripts/generate_test_data.py` uses `42` as the seed.

| Algorithm      | Sizes                              |
| -------------- | ---------------------------------- |
| Factorial      | 10, 50, 100, 250, 500, 800         |
| Tree traversal | 100, 500, 1000, 5000, 10000, 50000 |
| Merge sort     | 100, 500, 1000, 5000, 10000, 50000 |

`test_data/manifest.json` records each generated file's SHA-256 hash.

## 5. Number of repetitions
- 3 languages;
- 3 algorithms;
- 2 implementation modes;
- 6 input sizes per algorithm.

There are `3 * 3 * 2 * 6 = 108` configurations.

It is run 100 times for execution time, meaning `108 * 100 = 10800` timing measurements and 30 times for memory, producing `108 * 30 = 3240` memory tests.

## 6. Benchmark execution procedure

`scripts/run_time.py` and `scripts/run_memory.py` are run separately. Both:

1. Build only required language implementations.
2. Loads the test datasets and pairs input rows with expected answers.
3. Assigns the run a unique ID.
4. Randomises order of the tests
5. Write the results to a CSV.

Python and Rust spawn a new process for each test. One Java process is kept for each Java configuration and is reused in all 100 measurements, this only done in timing runs.

## 7. Timing and memory methodology

### Timing

Timing is done using each language's monotonic nanoseconds timer for before and after the function call.

### Java warm-up

Java warm up is done in groups of 100 calls. The benchmark expects at least 5 batches and at most 100 batches. Warm up ends if the deviation from the median of the last 5 runs is less than 15%.

### Memory

Memory tests use Valgrind Massif with (`--stacks=yes`) enabled. The summary includes the minimum, mean, median and snapshot count and peak usage of memory.


## 8. Known limitations

- Three chosen algorithms do not represent all possible recursive workloads.
- Startup cost for language is not part of the timed process, but may still be subject to any environmental effects.
- The Python and Rust implementations run a new process each time they are being timed, while Java uses a single JVM process regardless of the configuration.
- Massif reports on the behaviour of the process.
- Repeat timings are randomized, but not necessarily isolated from other uncontrolled effects of scheduling, CPU frequency, temperature and concurring workloads.
- The environment, rather than default language options alone, affects versions and allocator/JVM behaviours. The manifest contains this environment to make it auditable.
- Statistical tests and effect sizes describe these particular workloads and machines; they do not define absolute performance rankings.
