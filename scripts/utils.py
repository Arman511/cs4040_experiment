import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
DATASET_FILES = (
    "factorial.csv",
    "ans_factorial.csv",
    "tree.csv",
    "ans_tree.csv",
    "merge_sort.csv",
    "ans_merge_sort.csv",
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_terminal_codes(value: str) -> str:
    return ANSI_ESCAPE.sub("", value)


def command_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return strip_terminal_codes((result.stdout or result.stderr).strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_manifest() -> dict[str, dict[str, int | str]]:
    return {
        name: {
            "path": str((Path("test_data") / name).as_posix()),
            "sha256": sha256(ROOT / "test_data" / name),
            "bytes": (ROOT / "test_data" / name).stat().st_size,
        }
        for name in DATASET_FILES
    }


def runtime_manifest(languages: list[str], memory: bool = False) -> dict:
    runtimes: dict[str, dict[str, str]] = {}
    if "python" in languages:
        runtimes["python"] = {
            "executable": str(Path(sys.executable).relative_to(ROOT)),
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        }
    if "java" in languages:
        runtimes["java"] = {
            "java": command_output(["java", "-version"]),
            "javac": command_output(["javac", "-version"]),
            "maven": command_output(
                ["mvn", "-B", "-Dstyle.color=never", "-version"]
            ).splitlines()[0],
            "compiler_release": "25",
            "optimisation": (
                "JIT; cold process per measurement; no warm-up"
                if memory
                else "JIT; warm-up required before measurement"
            ),
        }
    if "rust" in languages:
        runtimes["rust"] = {
            "rustc": command_output(["rustc", "--version"]),
            "cargo": command_output(["cargo", "--version"]),
            "profile": "release",
            "optimisation": "cargo --release",
        }
    if memory:
        runtimes["valgrind"] = {"version": command_output(["valgrind", "--version"])}
    return runtimes


def new_run(
    benchmark_type: str,
    languages: list[str],
    algorithms: list[str],
    repetitions: int,
    order_seed: int,
    build_settings: dict,
) -> dict:
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    git_commit = command_output(["git", "rev-parse", "HEAD"])
    git_status = command_output(["git", "status", "--porcelain"])
    return {
        "run_id": run_id,
        "benchmark_type": benchmark_type,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "git_worktree_dirty": bool(git_status),
        "platform": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "languages": languages,
        "algorithms": algorithms,
        "modes": ["recursive", "iterative"],
        "repetitions": repetitions,
        "execution_order": {
            "randomised_within_repetition": True,
            "seed": order_seed,
        },
        "build_settings": build_settings,
        "runtimes": runtime_manifest(languages, memory=benchmark_type == "memory"),
        "datasets": dataset_manifest(),
    }


def finish_run(manifest: dict) -> None:
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = f"{manifest['benchmark_type']}_manifest_{manifest['run_id']}.json"
    path = RESULTS / name
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (RESULTS / f"{manifest['benchmark_type']}_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Manifest wrote to {path}")
