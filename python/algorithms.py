MOD = 1_000_000_007


def factorial_recursive(n):
    if n <= 1:
        return 1
    return (n * factorial_recursive(n - 1)) % MOD


def factorial_iterative(n):
    result = 1
    for i in range(2, n + 1):
        result = (result * i) % MOD
    return result


def tree_inorder_recursive(values):
    output = []

    def visit(i):
        if i >= len(values):
            return
        visit(2 * i + 1)
        output.append(values[i])
        visit(2 * i + 2)

    visit(0)
    return output


def tree_inorder_iterative(values):
    output, stack = [], []
    i = 0
    while stack or i < len(values):
        while i < len(values):
            stack.append(i)
            i = 2 * i + 1
        i = stack.pop()
        output.append(values[i])
        i = 2 * i + 2
    return output


def merge_sort_recursive(values):
    if len(values) <= 1:
        return values[:]
    mid = len(values) // 2
    left = merge_sort_recursive(values[:mid])
    right = merge_sort_recursive(values[mid:])
    return merge(left, right)


def merge_sort_iterative(values):
    result = values[:]
    stack = [(0, len(result), False)]
    while stack:
        start, end, children_sorted = stack.pop()
        if end - start <= 1:
            continue
        mid = (start + end) // 2
        if not children_sorted:
            stack.append((start, end, True))
            stack.append((mid, end, False))
            stack.append((start, mid, False))
            continue
        result[start:end] = merge(result[start:mid], result[mid:end])
    return result


def merge(left, right):
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out
