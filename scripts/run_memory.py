import argparse
import csv
from dataclasses import dataclass
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from utils import dataset_manifest, finish_run, new_run

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MASSIF_DIR = RESULTS / "massif"
LANGUAGES = ("python", "rust", "java")
ALGORITHMS = ("factorial", "tree", "merge_sort")
MODES = ("recursive", "iterative")


def run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def parse_massif(path: Path) -> list[dict]:
    snapshots = []
    current = None
    with path.open("r", encoding="utf-8", errors="replace") as source:
        for raw_line in source:
            line = raw_line.strip()
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
            elif current is not None and line.startswith("time="):
                current["time"] = int(line.split("=", 1)[1])
            elif current is not None and line.startswith("mem_heap_B="):
                current["heap_bytes"] = int(line.split("=", 1)[1])
            elif current is not None and line.startswith("mem_heap_extra_B="):
                current["heap_extra_bytes"] = int(line.split("=", 1)[1])
            elif current is not None and line.startswith("mem_stacks_B="):
                current["stack_bytes"] = int(line.split("=", 1)[1])
    if current is not None:
        current["total_bytes"] = (
            current["heap_bytes"] + current["heap_extra_bytes"] + current["stack_bytes"]
        )
        snapshots.append(current)
    return snapshots


@dataclass(frozen=True)
class Case:
    language: str
    algorithm: str
    mode: str
    size: int
    payload: int | Any
    dataset_file: str
    dataset_sha256: str


def iter_cases(algorithms: list[str], languages: list[str]):
    csv.field_size_limit(10 * 1024 * 1024)
    data_dir = ROOT / "test_data"
    datasets = dataset_manifest()
    for algorithm, filename, size_field in (
        ("factorial", "factorial.csv", "n"),
        ("tree", "tree.csv", "node_count"),
        ("merge_sort", "merge_sort.csv", "size"),
    ):
        if algorithm not in algorithms:
            continue
        with (data_dir / filename).open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                size = int(row[size_field])
                payload = (
                    size if algorithm == "factorial" else json.loads(row["values_json"])
                )
                for language in languages:
                    for mode in MODES:
                        yield Case(
                            language=language,
                            algorithm=algorithm,
                            mode=mode,
                            size=size,
                            payload=payload,
                            dataset_file=filename,
                            dataset_sha256=str(datasets[filename]["sha256"]),
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
    classpath = (java_dir / "target" / "classpath.txt").read_text().strip()
    return f"{java_dir / 'target' / 'classes'}:{classpath}"


def build_projects(languages: list[str]) -> str:
    RESULTS.mkdir(parents=True, exist_ok=True)
    MASSIF_DIR.mkdir(parents=True, exist_ok=True)
    if "rust" in languages:
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
    return build_java_classpath() if "java" in languages else ""


def profile_case(
    case: Case,
    repetition: int,
    run_id: str,
    results: dict,
    java_classpath: str,
) -> None:
    language = case.language
    algorithm = case.algorithm
    mode = case.mode
    size = case.size
    payload = case.payload
    tag = f"{language}_{algorithm}_{mode}_{size}_rep{repetition}"
    massif_path = MASSIF_DIR / f"{tag}.out"
    stderr_path = MASSIF_DIR / f"{tag}.stderr"
    report_path = MASSIF_DIR / f"{tag}.txt"
    input_path = MASSIF_DIR / f"input_{tag}.txt"
    input_path.write_text(
        (
            json.dumps(payload, separators=(",", ":"))
            if isinstance(payload, list)
            else str(payload)
        ),
        encoding="utf-8",
    )

    if language == "python":
        command = [
            sys.executable,
            str(ROOT / "python" / "profile_one.py"),
            algorithm,
            mode,
            f"@{input_path}",
        ]
    elif language == "rust":
        command = [
            str(ROOT / "rust" / "target" / "release" / "rust_benchmarks"),
            "--profile",
            algorithm,
            mode,
            f"@{input_path}",
        ]
    else:
        command = [
            "java",
            "-cp",
            java_classpath,
            "benchmark.ProfileOne",
            algorithm,
            mode,
            f"@{input_path}",
        ]

    with stderr_path.open("w", encoding="utf-8") as stderr:
        subprocess.run(
            [
                "valgrind",
                "--tool=massif",
                "--stacks=yes",
                f"--massif-out-file={massif_path}",
                *command,
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            check=True,
        )
    report = subprocess.run(
        ["ms_print", str(massif_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report_path.write_text(report.stdout, encoding="utf-8")
    snapshots = parse_massif(massif_path)
    if not snapshots:
        raise RuntimeError(f"No Massif snapshots found in {massif_path}")
    memory_values = [snapshot["total_bytes"] for snapshot in snapshots]
    peak = max(snapshots, key=lambda snapshot: snapshot["total_bytes"])
    common = {
        "run_id": run_id,
        "benchmark_type": "memory",
        "language": language,
        "algorithm": algorithm,
        "mode": mode,
        "input_size": size,
        "dataset_file": case.dataset_file,
        "dataset_sha256": case.dataset_sha256,
        "repetition": repetition,
    }
    results["records"].append(
        {
            **common,
            "peak_bytes": peak["total_bytes"],
            "peak_snapshot": peak["snapshot"],
            "peak_time": peak["time"],
            "minimum_bytes": min(memory_values),
            "average_bytes": statistics.mean(memory_values),
            "median_bytes": statistics.median(memory_values),
            "snapshot_count": len(snapshots),
            "massif_file": str(massif_path.relative_to(ROOT)),
        }
    )
    for snapshot in snapshots:
        results["snapshots"].append({**common, **snapshot})
    print(
        f"PROFILED {language} {algorithm} {mode} n={size} "
        f"peak={peak['total_bytes']}B snapshots={len(snapshots)}"
    )


def write_csv(path: Path, fieldnames: list[str], records: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as source:
        writer = csv.DictWriter(source, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible memory benchmarks.")
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--order-seed", type=int, default=2026)
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
    except FileNotFoundError:
        print("Valgrind is required for memory measurements.", file=sys.stderr)
        return 1

    java_classpath = build_projects(args.languages)
    cases = list(iter_cases(args.algorithms, args.languages))
    manifest = new_run(
        "memory",
        args.languages,
        args.algorithms,
        args.repetitions,
        args.order_seed,
        {
            "tool": "Valgrind Massif",
            "massif_options": ["--stacks=yes"],
            "metric": (
                "peak of mem_heap_B + mem_heap_extra_B + mem_stacks_B "
                "within the profiled process"
            ),
            "timing_separation": "Valgrind measurements are never used for timing",
            "java": "single ProfileOne process per measurement; no JIT warm-up",
            "rust": "cargo build --release",
        },
    )
    results = {"records": [], "snapshots": []}
    execution_random = random.Random(args.order_seed)
    for repetition in range(1, args.repetitions + 1):
        execution_order = cases[:]
        execution_random.shuffle(execution_order)
        for case in execution_order:
            profile_case(
                case,
                repetition,
                manifest["run_id"],
                results,
                java_classpath,
            )
        print(f"COMPLETED memory repetition {repetition}/{args.repetitions}")

    common_fields = [
        "run_id",
        "benchmark_type",
        "language",
        "algorithm",
        "mode",
        "input_size",
        "dataset_file",
        "dataset_sha256",
        "repetition",
    ]
    write_csv(
        RESULTS / "memory_usage.csv",
        common_fields
        + [
            "peak_memory_bytes",
            "peak_snapshot",
            "peak_time",
            "minimum_bytes",
            "average_bytes",
            "median_bytes",
            "snapshot_count",
            "massif_file",
        ],
        [
            {
                **record,
                "peak_memory_bytes": record["peak_bytes"],
            }
            for record in results["records"]
        ],
    )
    write_csv(
        RESULTS / "memory_snapshots.csv",
        common_fields
        + [
            "snapshot",
            "time",
            "heap_bytes",
            "heap_extra_bytes",
            "stack_bytes",
            "total_bytes",
        ],
        results["snapshots"],
    )
    manifest["configuration_count"] = len(cases)
    manifest["measurement_count"] = len(results["records"])
    manifest["expected_measurement_count"] = len(cases) * args.repetitions
    finish_run(manifest)
    print(f"Memory results wrote to {RESULTS / 'memory_usage.csv'}")
    print(f"Snapshot results wrote to {RESULTS / 'memory_snapshots.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
