import argparse
import csv
import json
import math
import random
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from utils import dataset_manifest, finish_run, new_run

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MODES = ("recursive", "iterative")


@dataclass(frozen=True)
class Case:
    language: str
    algorithm: str
    mode: str
    size: int
    input_path: Path
    answer_path: Path
    dataset_file: str
    dataset_sha256: str


def run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True, stdout=subprocess.DEVNULL)


def java_request(process: subprocess.Popen[str], command: str) -> str:
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("Java benchmark streams unavailable")
    try:
        process.stdin.write(command + "\n")
        process.stdin.flush()
    except BrokenPipeError as exc:
        raise RuntimeError("Java benchmark exited before receiving a command") from exc
    response = process.stdout.readline()
    if not response:
        raise RuntimeError("Java benchmark exited without a response")
    return response.strip()


def warm_up_java_case(
    process: subprocess.Popen[str],
    min_warmup_runs: int,
    max_warmup_runs: int,
    stability_threshold: float,
    batch_size: int,
) -> list[tuple[int, int, int]]:
    samples: list[tuple[int, int, int]] = []
    for batch in range(1, max_warmup_runs + 1):
        elapsed, compilation_after, compilation_before = map(
            int, java_request(process, f"warmup {batch_size}").split()
        )
        samples.append((elapsed, compilation_before, compilation_after))
        if batch < min_warmup_runs:
            continue
        recent = samples[-min_warmup_runs:]
        median = statistics.median(sample[0] for sample in recent)
        durations = sorted(sample[0] for sample in recent)
        if len(durations) >= 5:
            durations = durations[:-1]
        spread = max(abs(value - median) / median for value in durations)
        if spread <= stability_threshold and recent[0][1] == recent[-1][2]:
            print(
                f"WARMUP JAVA stabilised executions={batch * batch_size} "
                f"median_batch_ns={median} spread={spread:.3f}"
            )
            return samples
    raise RuntimeError(
        f"Java warm-up did not stabilise after {max_warmup_runs} batches"
    )


def parse_measurements(output: str, expected_count: int) -> list[int]:
    try:
        values = [int(value) for value in output.replace(",", " ").split()]
    except ValueError as exc:
        raise RuntimeError(f"Invalid timing output: {output!r}") from exc
    if len(values) != expected_count or any(value < 0 for value in values):
        raise RuntimeError(f"Expected {expected_count} measurements, got {output!r}")
    return values


def iter_inputs(algorithms: list[str]):
    csv.field_size_limit(10 * 1024 * 1024)
    datasets = dataset_manifest()
    data_dir = ROOT / "test_data"
    for algorithm, size_field in (
        ("factorial", "n"),
        ("tree", "node_count"),
        ("merge_sort", "size"),
    ):
        if algorithm not in algorithms:
            continue
        with (
            (data_dir / f"{algorithm}.csv").open(
                newline="", encoding="utf-8"
            ) as inputs,
            (data_dir / f"ans_{algorithm}.csv").open(
                newline="", encoding="utf-8"
            ) as answers,
        ):
            for row, answer in zip_longest(
                csv.DictReader(inputs), csv.DictReader(answers)
            ):
                if (
                    row is None
                    or answer is None
                    or row[size_field] != answer[size_field]
                ):
                    raise ValueError(
                        f"Input and answer rows do not match for {algorithm}"
                    )
                size = int(row[size_field])
                payload = (
                    size if algorithm == "factorial" else json.loads(row["values_json"])
                )
                expected = json.loads(answer["result_json"])
                dataset_file = f"{algorithm}.csv"
                yield (
                    algorithm,
                    size,
                    payload,
                    expected,
                    dataset_file,
                    str(datasets[dataset_file]["sha256"]),
                )


def build_java_classpath() -> str:
    java_dir = ROOT / "java"
    run(
        [
            "mvn",
            "-q",
            "package",
            "dependency:build-classpath",
            "-Dmdep.outputFile=target/classpath.txt",
        ],
        cwd=java_dir,
    )
    classpath = (java_dir / "target" / "classpath.txt").read_text().strip()
    return f"{java_dir / 'target' / 'classes'}:{classpath}"


def prepare_environment(languages: list[str]) -> str:
    RESULTS.mkdir(exist_ok=True)
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


def build_command(case: Case, repetitions: int, java_classpath: str) -> list[str]:
    raw = f"@{case.input_path}"
    if case.language == "python":
        return [
            sys.executable,
            str(ROOT / "python" / "time_one.py"),
            case.algorithm,
            case.mode,
            raw,
            str(case.answer_path),
            str(repetitions),
        ]
    if case.language == "rust":
        return [
            str(ROOT / "rust" / "target" / "release" / "rust_benchmarks"),
            "--timing",
            case.algorithm,
            case.mode,
            raw,
            str(case.answer_path),
            str(repetitions),
        ]
    return [
        "java",
        "-cp",
        java_classpath,
        "benchmark.TimeOne",
        case.algorithm,
        case.mode,
        raw,
        str(case.answer_path),
    ]


def close_java_process(
    process: subprocess.Popen[str],
) -> None:
    if process.stdin is not None:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Java benchmark failed during shutdown")


def write_timing_rows(rows: list[tuple]) -> Path:
    path = RESULTS / "time_usage.csv"
    with path.open("w", newline="", encoding="utf-8") as source:
        writer = csv.writer(source)
        writer.writerow(
            [
                "run_id",
                "benchmark_type",
                "language",
                "algorithm",
                "mode",
                "input_size",
                "dataset_file",
                "dataset_sha256",
                "repetition",
                "execution_time_ns",
            ]
        )
        writer.writerows(rows)
    return path


def write_warmup_rows(rows: list[tuple]) -> Path:
    path = RESULTS / "java_warmup.csv"
    with path.open("w", newline="", encoding="utf-8") as source:
        writer = csv.writer(source)
        writer.writerow(
            [
                "run_id",
                "algorithm",
                "mode",
                "input_size",
                "batch",
                "batch_size",
                "elapsed_ns",
                "compilation_before_ms",
                "compilation_after_ms",
            ]
        )
        writer.writerows(rows)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible timing benchmarks.")
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--order-seed", type=int, default=2026)
    parser.add_argument("--warmup-runs", type=int, default=100)
    parser.add_argument("--warmup-min-runs", type=int, default=5)
    parser.add_argument("--warmup-stability-threshold", type=float, default=0.15)
    parser.add_argument("--warmup-batch-size", type=int, default=100)
    parser.add_argument(
        "--languages",
        nargs="*",
        default=["python", "rust", "java"],
        choices=["python", "rust", "java"],
    )
    parser.add_argument(
        "--algorithms",
        nargs="*",
        default=["factorial", "tree", "merge_sort"],
        choices=["factorial", "tree", "merge_sort"],
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.warmup_runs < 1:
        parser.error("--warmup-runs must be at least 1")
    if not 2 <= args.warmup_min_runs <= args.warmup_runs:
        parser.error("--warmup-min-runs must be between 2 and --warmup-runs")
    if (
        not math.isfinite(args.warmup_stability_threshold)
        or args.warmup_stability_threshold < 0
    ):
        parser.error("--warmup-stability-threshold must be finite and non-negative")
    if args.warmup_batch_size < 1:
        parser.error("--warmup-batch-size must be at least 1")

    manifest = new_run(
        "timing",
        args.languages,
        args.algorithms,
        args.repetitions,
        args.order_seed,
        {
            "python": "no optimisation flags; operation timers exclude process startup",
            "java": "Maven compiler release 25; JVM process reused across measurements",
            "rust": "cargo build --release; operation timers exclude process startup",
            "java_warmup": {
                "maximum_batches": args.warmup_runs,
                "minimum_batches": args.warmup_min_runs,
                "batch_size": args.warmup_batch_size,
                "relative_spread_threshold": args.warmup_stability_threshold,
                "criterion": (
                    "relative spread <= threshold after excluding the largest "
                    "sample when at least five samples exist, and total compilation "
                    "time is unchanged across the stability window"
                ),
            },
        },
    )
    java_classpath = prepare_environment(args.languages)
    rows: list[tuple] = []
    warmup_rows: list[tuple] = []
    java_processes: dict[tuple[str, str, int], subprocess.Popen[str]] = {}

    with tempfile.TemporaryDirectory(prefix="benchmark-input-") as temp_dir:
        temp = Path(temp_dir)
        cases: list[Case] = []
        for case_index, (
            algorithm,
            size,
            payload,
            expected,
            dataset_file,
            dataset_sha256,
        ) in enumerate(iter_inputs(args.algorithms)):
            input_path = temp / f"input-{case_index}.txt"
            answer_path = temp / f"answer-{case_index}.json"
            input_path.write_text(
                (
                    str(payload)
                    if isinstance(payload, int)
                    else json.dumps(payload, separators=(",", ":"))
                ),
                encoding="utf-8",
            )
            answer_path.write_text(
                json.dumps(expected, separators=(",", ":")), encoding="utf-8"
            )
            for language in args.languages:
                for mode in MODES:
                    cases.append(
                        Case(
                            language,
                            algorithm,
                            mode,
                            size,
                            input_path,
                            answer_path,
                            dataset_file,
                            dataset_sha256,
                        )
                    )

        try:
            for case in cases:
                if case.language != "java":
                    continue
                process = subprocess.Popen(
                    build_command(case, 1, java_classpath),
                    cwd=ROOT,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                )
                java_processes[(case.algorithm, case.mode, case.size)] = process
                print(
                    f"WARMUP {case.language} {case.algorithm} {case.mode} n={case.size}"
                )
                for batch, (elapsed, before, after) in enumerate(
                    warm_up_java_case(
                        process,
                        args.warmup_min_runs,
                        args.warmup_runs,
                        args.warmup_stability_threshold,
                        args.warmup_batch_size,
                    ),
                    1,
                ):
                    warmup_rows.append(
                        (
                            manifest["run_id"],
                            case.algorithm,
                            case.mode,
                            case.size,
                            batch,
                            args.warmup_batch_size,
                            elapsed,
                            before,
                            after,
                        )
                    )

            order_random = random.Random(args.order_seed)
            for repetition in range(1, args.repetitions + 1):
                execution_order = cases[:]
                order_random.shuffle(execution_order)
                for case in execution_order:
                    if case.language == "java":
                        process = java_processes[(case.algorithm, case.mode, case.size)]
                        elapsed = parse_measurements(
                            java_request(process, "measure 1"), 1
                        )[0]
                    else:
                        result = subprocess.run(
                            build_command(case, 1, java_classpath),
                            cwd=ROOT,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        elapsed = parse_measurements(result.stdout, 1)[0]
                    rows.append(
                        (
                            manifest["run_id"],
                            "timing",
                            case.language,
                            case.algorithm,
                            case.mode,
                            case.size,
                            case.dataset_file,
                            case.dataset_sha256,
                            repetition,
                            elapsed,
                        )
                    )
                print(f"COMPLETED timing repetition {repetition}/{args.repetitions}")
        finally:
            for process in java_processes.values():
                close_java_process(process)

    manifest["configuration_count"] = len(cases)
    manifest["measurement_count"] = len(rows)
    manifest["expected_measurement_count"] = len(cases) * args.repetitions
    output = write_timing_rows(rows)
    warmup_output = write_warmup_rows(warmup_rows) if warmup_rows else None
    finish_run(manifest)
    print(f"Timing results wrote to {output}")
    if warmup_output:
        print(f"Java warm-up logs wrote to {warmup_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
