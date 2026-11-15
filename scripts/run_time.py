import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
import tempfile
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, stdout=subprocess.DEVNULL)


def warm_up_java_case(
    process: subprocess.Popen[str],
    min_warmup_runs: int,
    max_warmup_runs: int,
    stability_threshold: float,
    batch_size: int,
) -> list[tuple[int, int, int]]:
    samples: list[tuple[int, int, int]] = []
    for batch in range(1, max_warmup_runs + 1):
        response = java_request(process, f"warmup {batch_size}")
        values = response.split()
        elapsed, compilation_after, compilation_before = map(int, values)
        samples.append((elapsed, compilation_before, compilation_after))
        print(f"""WARMUP batch={batch} executions={batch * batch_size} 
batch_ns={elapsed} compilation_ms={compilation_after}""")
        if batch < min_warmup_runs:
            continue

        recent = samples[-min_warmup_runs:]
        median = statistics.median(sample[0] for sample in recent)
        durations = sorted(sample[0] for sample in recent)
        if len(durations) >= 5:
            durations = durations[:-1]
        relative_spread = max(abs(value - median) / median for value in durations)
        if relative_spread <= stability_threshold and recent[0][1] == recent[-1][2]:
            print(f"""WARMUP JAVA stabilised after {batch * batch_size} executions 
median_batch_ns={median} spread={relative_spread:.3f}""")
            return samples

    raise RuntimeError(f"Java warm-up did not stabilise at {max_warmup_runs} runs")


def java_request(process: subprocess.Popen[str], command: str) -> str:
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("streams unavailable")
    try:
        process.stdin.write(command + "\n")
        process.stdin.flush()
    except BrokenPipeError as exc:
        raise RuntimeError("benchmark exited before receiving a command") from exc
    response = process.stdout.readline()
    if not response:
        raise RuntimeError("exited without a response")
    return response.strip()


def parse_measurements(output: str, repetitions: int) -> list[int]:
    try:
        values = [int(value) for value in output.split()]
    except ValueError as exc:
        raise RuntimeError(f"Invalid timing output: {output!r}") from exc
    if len(values) != repetitions or any(value < 0 for value in values):
        raise RuntimeError(f"Expected {repetitions}, got {output!r}")
    return values


def measure_case(
    cmd: list[str], language: str, repetitions: int, args: argparse.Namespace
) -> tuple[list[int], list[tuple[int, int, int]]]:
    if language != "java":
        result = subprocess.run(
            [*cmd, str(repetitions)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        return parse_measurements(result.stdout, repetitions), []

    with subprocess.Popen(
        cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as process:
        warmup = warm_up_java_case(
            process,
            min_warmup_runs=args.warmup_min_runs,
            max_warmup_runs=args.warmup_runs,
            stability_threshold=args.warmup_stability_threshold,
            batch_size=args.warmup_batch_size,
        )
        response = java_request(process, f"measure {repetitions}")
        measurements = parse_measurements(response.replace(",", " "), repetitions)
        if process.stdin is None:
            raise RuntimeError("stdin unavailable")
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Java benchmark failed after measurement")
        return measurements, warmup


def iter_cases():
    csv.field_size_limit(10 * 1024 * 1024)

    data_dir = ROOT / "test_data"
    for algorithm, size_field in (
        ("factorial", "n"),
        ("tree", "node_count"),
        ("merge_sort", "size"),
    ):
        with (
            (data_dir / f"{algorithm}.csv").open(newline="", encoding="utf-8") as inputs,
            (data_dir / f"ans_{algorithm}.csv").open(newline="", encoding="utf-8") as answers,
        ):
            for row, answer in zip_longest(csv.DictReader(inputs), csv.DictReader(answers)):
                if row is None or answer is None or row[size_field] != answer[size_field]:
                    raise ValueError(f"Input and answer rows do not match for {algorithm}")
                size = int(row[size_field])
                payload = size if algorithm == "factorial" else json.loads(row["values_json"])
                expected = json.loads(answer["result_json"])
                if algorithm == "factorial":
                    if type(expected) is not int:
                        raise ValueError(f"Invalid factorial answer for n={size}")
                elif not isinstance(payload, list) or not isinstance(expected, list) or len(expected) != len(payload):
                    raise ValueError(f"Invalid {algorithm} answer for n={size}")
                yield algorithm, size, payload, expected


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
    classpath_path = java_dir / "target" / "classpath.txt"
    return f"{java_dir / 'target' / 'classes'}:{classpath_path.read_text(encoding='utf-8').strip()}"


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


def build_command(
    language: str, algorithm: str, mode: str, input_file: Path, answer_file: Path, java_cp: str
) -> list[str]:
    raw = f"@{input_file}"
    if language == "python":
        return [
            sys.executable,
            str(ROOT / "python" / "time_one.py"),
            algorithm,
            mode,
            raw,
            str(answer_file),
        ]
    elif language == "rust":
        return [
            str(ROOT / "rust" / "target" / "release" / "rust_benchmarks"),
            "--timing",
            algorithm,
            mode,
            raw,
            str(answer_file),
        ]
    return ["java", "-cp", java_cp, "benchmark.TimeOne", algorithm, mode, raw, str(answer_file)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run timing benchmarks across all languages, algorithms, and modes."
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--warmup-min-runs",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--warmup-stability-threshold",
        type=float,
        default=0.15,
    )
    parser.add_argument(
        "--warmup-batch-size",
        type=int,
        default=100,
    )
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
    if args.warmup_min_runs < 2:
        parser.error("--warmup-min-runs must be at least 2")
    if args.warmup_min_runs > args.warmup_runs:
        parser.error("--warmup-min-runs cannot exceed --warmup-runs")
    if (
        not math.isfinite(args.warmup_stability_threshold)
        or args.warmup_stability_threshold < 0
    ):
        parser.error("--warmup-stability-threshold must be finite and non-negative")
    if args.warmup_batch_size < 1:
        parser.error("--warmup-batch-size must be at least 1")

    env = prepare_environment(args.languages)
    rows: list[tuple[str, str, str, int, int, int]] = []
    warmup_rows: list[tuple[str, str, int, int, int, int, int, int]] = []

    with tempfile.TemporaryDirectory(prefix="benchmark-input-") as temp_dir:
        input_file = Path(temp_dir) / "input.txt"
        answer_file = Path(temp_dir) / "answer.json"
        for algorithm, size, payload, expected in iter_cases():
            if algorithm not in args.algorithms:
                continue
            if isinstance(payload, list):
                raw = json.dumps(payload, separators=(",", ":"))
            elif isinstance(payload, int):
                raw = str(payload)
            else:
                raise TypeError(f"Unsupported payload type: {type(payload)!r}")
            input_file.write_text(raw, encoding="utf-8")
            answer_file.write_text(json.dumps(expected, separators=(",", ":")), encoding="utf-8")
            for language in args.languages:
                for mode in ("recursive", "iterative"):
                    cmd = build_command(language, algorithm, mode, input_file, answer_file, env)
                    print(f"BENCHMARK {language} {algorithm} {mode} n={size}")
                    measurements, warmup = measure_case(
                        cmd, language, args.repetitions, args
                    )
                    for batch, (elapsed, before, after) in enumerate(warmup, 1):
                        warmup_rows.append(
                            (
                                algorithm,
                                mode,
                                size,
                                batch,
                                args.warmup_batch_size,
                                elapsed,
                                before,
                                after,
                            )
                        )
                    for repetition, elapsed in enumerate(measurements, 1):
                        rows.append(
                            (language, algorithm, mode, size, repetition, elapsed)
                        )
                        print(
                            f"TIMED {language} {algorithm} {mode} n={size} rep={repetition} elapsed_ns={elapsed}"
                        )

    out_path = RESULTS / "time_usage.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["language", "algorithm", "mode", "input_size", "repetition", "elapsed_ns"]
        )
        writer.writerows(rows)

    print(f"Timing results wrote to {out_path}")
    if "java" in args.languages:
        warmup_path = RESULTS / "java_warmup.csv"
        with warmup_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
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
            writer.writerows(warmup_rows)
        print(f"Java warm-up logs wrote to {warmup_path}")
    return 0


if __name__ == "__main__":
    main()
