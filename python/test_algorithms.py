import csv
import json
import math
import random
import unittest
from pathlib import Path

from algorithms import (
    MOD,
    factorial_iterative,
    factorial_recursive,
    merge_sort_iterative,
    merge_sort_recursive,
    tree_inorder_iterative,
    tree_inorder_recursive,
)

DATA = Path(__file__).resolve().parent.parent / "test_data"
csv.field_size_limit(10 * 1024 * 1024)


def rows(name):
    with (DATA / name).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


class AlgorithmCorrectnessTests(unittest.TestCase):
    def test_factorial_minimum_small_random_and_generated_answers(self):
        for n in [0, 1, 2, 10, 250]:
            expected = math.factorial(n) % MOD
            self.assertEqual(factorial_recursive(n), expected)
            self.assertEqual(factorial_iterative(n), expected)

        rng = random.Random(2026)
        for n in (rng.randrange(0, 801) for _ in range(100)):
            expected = math.factorial(n) % MOD
            self.assertEqual(factorial_recursive(n), expected)
            self.assertEqual(factorial_iterative(n), expected)

        inputs = rows("factorial.csv")
        answers = rows("ans_factorial.csv")
        self.assertEqual(len(inputs), len(answers))
        for input_row, answer_row in zip(inputs, answers):
            n = int(input_row["n"])
            self.assertEqual(input_row["n"], answer_row["n"])
            expected = json.loads(answer_row["result_json"])
            self.assertEqual(factorial_recursive(n), expected)
            self.assertEqual(factorial_iterative(n), expected)
        self.assertEqual(int(inputs[-1]["n"]), 800)

    def test_tree_minimum_small_random_and_generated_answers(self):
        for values in ([], [1], [4, 2, 6, 1, 3, 5, 7]):
            expected = tree_reference(values)
            self.assertEqual(tree_inorder_recursive(values), expected)
            self.assertEqual(tree_inorder_iterative(values), expected)

        rng = random.Random(2026)
        for size in [3, 17, 128, 1024]:
            values = [rng.randint(-10_000, 10_000) for _ in range(size)]
            expected = tree_reference(values)
            self.assertEqual(tree_inorder_recursive(values), expected)
            self.assertEqual(tree_inorder_iterative(values), expected)

        inputs = rows("tree.csv")
        answers = rows("ans_tree.csv")
        self.assertEqual(len(inputs), len(answers))
        for input_row, answer_row in zip(inputs, answers):
            self.assertEqual(input_row["node_count"], answer_row["node_count"])
            values = json.loads(input_row["values_json"])
            expected = json.loads(answer_row["result_json"])
            self.assertEqual(tree_inorder_recursive(values), expected)
            self.assertEqual(tree_inorder_iterative(values), expected)
        self.assertEqual(int(inputs[-1]["node_count"]), 50_000)

    def test_merge_sort_minimum_small_random_and_generated_answers(self):
        for values in ([], [1], [2, 1], [5, -1, 5, 3, 0]):
            self.assertEqual(merge_sort_recursive(values), sorted(values))
            self.assertEqual(merge_sort_iterative(values), sorted(values))

        rng = random.Random(2026)
        for size in [3, 17, 128, 1024]:
            values = [rng.randint(-10_000, 10_000) for _ in range(size)]
            self.assertEqual(merge_sort_recursive(values), sorted(values))
            self.assertEqual(merge_sort_iterative(values), sorted(values))

        inputs = rows("merge_sort.csv")
        answers = rows("ans_merge_sort.csv")
        self.assertEqual(len(inputs), len(answers))
        for input_row, answer_row in zip(inputs, answers):
            self.assertEqual(input_row["size"], answer_row["size"])
            values = json.loads(input_row["values_json"])
            expected = json.loads(answer_row["result_json"])
            self.assertEqual(merge_sort_recursive(values), expected)
            self.assertEqual(merge_sort_iterative(values), expected)
        self.assertEqual(int(inputs[-1]["size"]), 50_000)


def tree_reference(values):
    output = []
    stack = []
    index = 0
    while stack or index < len(values):
        while index < len(values):
            stack.append(index)
            index = 2 * index + 1
        index = stack.pop()
        output.append(values[index])
        index = 2 * index + 2
    return output


if __name__ == "__main__":
    unittest.main()
