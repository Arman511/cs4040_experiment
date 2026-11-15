import json
import sys
import time

from algorithms import (
    factorial_iterative,
    factorial_recursive,
    merge_sort_iterative,
    merge_sort_recursive,
    tree_inorder_iterative,
    tree_inorder_recursive,
)


def main():
    algorithm, mode, raw, answer_file, repetitions = sys.argv[1:]
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as source:
            raw = source.read()
    payload = int(raw) if algorithm == "factorial" else json.loads(raw)
    with open(answer_file, encoding="utf-8") as source:
        expected = json.load(source)
    operation = {
        ("factorial", "recursive"): factorial_recursive,
        ("factorial", "iterative"): factorial_iterative,
        ("tree", "recursive"): tree_inorder_recursive,
        ("tree", "iterative"): tree_inorder_iterative,
        ("merge_sort", "recursive"): merge_sort_recursive,
        ("merge_sort", "iterative"): merge_sort_iterative,
    }[(algorithm, mode)]
    for _ in range(5):
        operation(payload)
    for _ in range(int(repetitions)):
        start = time.perf_counter_ns()
        result = operation(payload)
        elapsed = time.perf_counter_ns() - start
        if result != expected:
            raise ValueError(f"Incorrect result for {algorithm} {mode}")
        print(elapsed)
        del result


if __name__ == "__main__":
    main()
