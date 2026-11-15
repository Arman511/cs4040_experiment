import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MASSIF_DIR = RESULTS / "massif"

LANGUAGES = ("python", "rust", "java")
ALGORITHMS = ("factorial", "tree", "merge_sort")
MODES = ("recursive", "iterative")


def run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def parse_massif(massif_path: Path) -> list[dict]:
    snapshots = []
    current = None

    with massif_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()

            if line.startswith("snapshot="):
                if current is not None:
                    current["total_bytes"] = (
                        current["heap_bytes"]
                        + current["heap_extra_bytes"]
                        + current["stack_bytes"]
                    )
                    snapshots.append(current)

                current = {
                    "snapshot": int(line.split("=", 1)[1]),
                    "time": 0,
                    "heap_bytes": 0,
                    "heap_extra_bytes": 0,
                    "stack_bytes": 0,
                }

            elif current is not None:
                if line.startswith("time="):
                    current["time"] = int(line.split("=", 1)[1])

                elif line.startswith("mem_heap_B="):
                    current["heap_bytes"] = int(line.split("=", 1)[1])

                elif line.startswith("mem_heap_extra_B="):
                    current["heap_extra_bytes"] = int(line.split("=", 1)[1])

                elif line.startswith("mem_stacks_B="):
                    current["stack_bytes"] = int(line.split("=", 1)[1])

    if current is not None:
        current["total_bytes"] = (
            current["heap_bytes"] + current["heap_extra_bytes"] + current["stack_bytes"]
        )
        snapshots.append(current)

    return snapshots


def iter_cases():
    csv.field_size_limit(10 * 1024 * 1024)

    data_dir = ROOT / "test_data"

    with (data_dir / "factorial.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield ("factorial", int(row["n"]), int(row["n"]))

    with (data_dir / "tree.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield (
                "tree",
                int(row["node_count"]),
                json.loads(row["values_json"]),
            )

    with (data_dir / "merge_sort.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield (
                "merge_sort",
                int(row["size"]),
                json.loads(row["values_json"]),
            )


def build_java_classpath() -> str:

    java_dir = ROOT / "java"

    run(
        [
            "mvn",
            "-q",
            "clean",
            "package",
            "dependency:build-classpath",
            "-Dmdep.outputFile=target/classpath.txt",
        ],
        cwd=java_dir,
    )

    classpath_path = java_dir / "target" / "classpath.txt"

    return f"{java_dir / 'target' / 'classes'}:{classpath_path.read_text(encoding='utf-8').strip()}"


def build_project() -> str:
    RESULTS.mkdir(parents=True, exist_ok=True)
    MASSIF_DIR.mkdir(parents=True, exist_ok=True)

    run(
        [
            "cargo",
            "build",
            "--release",
            "--manifest-path",
            str(ROOT / "rust" / "Cargo.toml"),
        ],
        cwd=ROOT,
    )

    java_cp = build_java_classpath()

    return java_cp


def profile_case(
    language: str,
    algorithm: str,
    mode: str,
    payload,
    size: int,
    repetition: int,
    results: dict,
    java_cp: str,
) -> None:
    tag = f"{language}_{algorithm}_{mode}_" f"{size}_rep{repetition}"

    massif_path = MASSIF_DIR / f"{tag}.out"
    stderr_path = MASSIF_DIR / f"{tag}.stderr"
    report_path = MASSIF_DIR / f"{tag}.txt"
    input_file = MASSIF_DIR / f"input_{tag}.txt"

    input_file.write_text(
        (
            json.dumps(payload, separators=(",", ":"))
            if isinstance(payload, list)
            else str(payload)
        ),
        encoding="utf-8",
    )

    if language == "python":
        cmd = [
            "python3",
            str(ROOT / "python" / "profile_one.py"),
            algorithm,
            mode,
            f"@{input_file}",
        ]
    elif language == "rust":
        cmd = [
            str(ROOT / "rust" / "target" / "release" / "rust_benchmarks"),
            "--profile",
            algorithm,
            mode,
            f"@{input_file}",
        ]
    else:
        cmd = [
            "java",
            "-cp",
            java_cp,
            "benchmark.ProfileOne",
            algorithm,
            mode,
            f"@{input_file}",
        ]

    with stderr_path.open("w", encoding="utf-8") as err_file:
        subprocess.run(
            [
                "valgrind",
                "--tool=massif",
                "--stacks=yes",
                f"--massif-out-file={massif_path}",
                *cmd,
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=err_file,
            check=True,
        )

    report = subprocess.run(
        ["ms_print", str(massif_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    report_path.write_text(report.stdout, encoding="utf-8")

    snapshots = parse_massif(massif_path)

    if not snapshots:
        raise RuntimeError(f"No Massif snapshots found in {massif_path}")

    memory_values = [snapshot["total_bytes"] for snapshot in snapshots]

    peak_snapshot = max(
        snapshots,
        key=lambda snapshot: snapshot["total_bytes"],
    )

    results["records"].append(
        {
            "language": language,
            "algorithm": algorithm,
            "mode": mode,
            "input_size": size,
            "repetition": repetition,
            "peak_bytes": peak_snapshot["total_bytes"],
            "peak_snapshot": peak_snapshot["snapshot"],
            "peak_time": peak_snapshot["time"],
            "minimum_bytes": min(memory_values),
            "average_bytes": statistics.mean(memory_values),
            "median_bytes": statistics.median(memory_values),
            "snapshot_count": len(snapshots),
            "massif_file": str(massif_path.relative_to(ROOT)),
        }
    )

    for snapshot in snapshots:
        results["snapshots"].append(
            {
                "language": language,
                "algorithm": algorithm,
                "mode": mode,
                "input_size": size,
                "repetition": repetition,
                **snapshot,
            }
        )

    print(
        f"PROFILED {language} {algorithm} {mode} n={size} peak={peak_snapshot['total_bytes']}B average={statistics.mean(memory_values):.2f}B snapshots={len(snapshots)}"
    )


def write_summary_csv(records: list[dict]) -> None:
    out_path = RESULTS / "memory_usage.csv"

    fieldnames = [
        "language",
        "algorithm",
        "mode",
        "input_size",
        "repetition",
        "peak_bytes",
        "peak_snapshot",
        "peak_time",
        "minimum_bytes",
        "average_bytes",
        "median_bytes",
        "snapshot_count",
        "massif_file",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Summary results written to {out_path}")


def write_snapshots_csv(snapshots: list[dict]) -> None:
    out_path = RESULTS / "memory_snapshots.csv"

    fieldnames = [
        "language",
        "algorithm",
        "mode",
        "input_size",
        "repetition",
        "snapshot",
        "time",
        "heap_bytes",
        "heap_extra_bytes",
        "stack_bytes",
        "total_bytes",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(snapshots)

    print(f"Snapshot results written to {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repetitions",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--languages",
        nargs="*",
        default=list(LANGUAGES),
        choices=LANGUAGES,
    )

    parser.add_argument(
        "--algorithms",
        nargs="*",
        default=list(ALGORITHMS),
        choices=ALGORITHMS,
    )

    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    try:
        subprocess.run(
            ["valgrind", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except Exception:
        print(
            "install valgrind",
        )
        return 1

    try:
        java_cp = build_project()

        results = {
            "records": [],
            "snapshots": [],
        }

        for algorithm, size, payload in iter_cases():

            if algorithm not in args.algorithms:
                continue

            for language in args.languages:

                for mode in MODES:

                    for repetition in range(
                        1,
                        args.repetitions + 1,
                    ):
                        profile_case(
                            language,
                            algorithm,
                            mode,
                            payload,
                            size,
                            repetition,
                            results,
                            java_cp,
                        )

        write_summary_csv(results["records"])
        write_snapshots_csv(results["snapshots"])

    except Exception as e:
        print(f"Benchmark failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    main()
