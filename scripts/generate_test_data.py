import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test_data"
SEED = 42


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def generate_answers():
    csv.field_size_limit(10 * 1024 * 1024)
    with (OUT / "factorial.csv").open(newline="", encoding="utf-8") as f:
        rows = [
            [row["n"], math.factorial(int(row["n"])) % 1_000_000_007]
            for row in csv.DictReader(f)
        ]
    write_csv("ans_factorial.csv", ["n", "result_json"], rows)

    for algorithm, size_field in (("tree", "node_count"), ("merge_sort", "size")):
        answers = []
        with (OUT / f"{algorithm}.csv").open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                values = json.loads(row["values_json"])
                if algorithm == "tree":
                    result = []

                    def visit(index):
                        if index < len(values):
                            visit(2 * index + 1)
                            result.append(values[index])
                            visit(2 * index + 2)

                    visit(0)
                else:
                    result = sorted(values)
                answers.append(
                    [row[size_field], json.dumps(result, separators=(",", ":"))]
                )
        write_csv(f"ans_{algorithm}.csv", [size_field, "result_json"], answers)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    factorial_sizes = [10, 50, 100, 250, 500, 800]
    write_csv("factorial.csv", ["n"], [[n] for n in factorial_sizes])

    tree_sizes = [100, 500, 1000, 5000, 10000, 50000]
    tree_rows = []
    for n in tree_sizes:
        values = rng.sample(range(1, n * 20 + 1), n)
        tree_rows.append([n, json.dumps(values, separators=(",", ":"))])
    write_csv("tree.csv", ["node_count", "values_json"], tree_rows)

    merge_sizes = [100, 500, 1000, 5000, 10000, 50000]
    merge_rows = []
    for n in merge_sizes:
        values = [rng.randint(-100000, 100000) for _ in range(n)]
        merge_rows.append([n, json.dumps(values, separators=(",", ":"))])
    write_csv("merge_sort.csv", ["size", "values_json"], merge_rows)

    generate_answers()
    print(f"Generated shared datasets in {OUT}")


if __name__ == "__main__":
    main()
