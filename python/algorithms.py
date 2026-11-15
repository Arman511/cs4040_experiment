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
    width = 1
    while width < len(result):
        merged = []
        for start in range(0, len(result), 2 * width):
            left = result[start : start + width]
            right = result[start + width : start + 2 * width]
            merged.extend(merge(left, right))
        result = merged
        width *= 2
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
