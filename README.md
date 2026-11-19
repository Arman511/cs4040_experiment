# Recursive versus iterative benchmark experiment

This repo compares recursive and iterative implementations of factorial,
binary tree traversal, and merge sort in Python, Java, and Rust.

## Reproduce the experiment

Generate the test datasets first:

```bash
uv run scripts/generate_test_data.py
```

Run correctness tests:

```bash
uv run python -m unittest discover -s python -p "test_*.py"
mvn -f java/pom.xml test
cargo test --manifest-path rust/Cargo.toml
```

Run the two measurements separately:

```bash
uv run scripts/run_time.py
uv run scripts/run_memory.py
```

Timing defaults to 100 repetitions per configuration. Memory defaults to 30
repetitions per configuration. Both use a fixed seed of `2026` to
randomise configuration run order. The dataset generator uses seed `42`.

The scripts write:

- `results/time_usage.csv` and `results/timing_manifest.json`
- `results/memory_usage.csv`, `results/memory_snapshots.csv`, and
  `results/memory_manifest.json`
- a uniquely named manifest for every run

Memory test uses Valgrind Massif. Each manifest records the Git commit, worktree state,
runtime/compiler versions, build settings, repetition count, order seed, and
SHA-256 hashes of the shared test datasets.

Run the statistical analysis from the repository root:

```bash
Rscript analysis/main.r
```

## Experimental scale

| Dimension                 |  Count |
| ------------------------- | -----: |
| Languages                 |      3 |
| Algorithms                |      3 |
| Implementation modes      |      2 |
| Input sizes per algorithm |      6 |
| Configurations            |    108 |
| Timing measurements       | 10,800 |
| Memory measurements       |  3,240 |
| Total measurements        | 14,040 |

See [docs/experimental_design.md](docs/experimental_design.md) for the
complete algorithm specifications, benchmark procedure, warm-up policy, and
known limitations.
