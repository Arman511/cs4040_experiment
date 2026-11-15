import json
import sys
from algorithms import *

algorithm, mode, raw = sys.argv[1:4]
if raw.startswith("@"):
    raw = open(raw[1:], encoding="utf-8").read()
payload = int(raw) if algorithm == "factorial" else json.loads(raw)

functions = {
    ("factorial", "recursive"): factorial_recursive,
    ("factorial", "iterative"): factorial_iterative,
    ("tree", "recursive"): tree_inorder_recursive,
    ("tree", "iterative"): tree_inorder_iterative,
    ("merge_sort", "recursive"): merge_sort_recursive,
    ("merge_sort", "iterative"): merge_sort_iterative,
}
functions[(algorithm, mode)](payload)
