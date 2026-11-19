package benchmark;

import java.util.*;

public final class Algorithms {
    private static final long MOD = 1_000_000_007L;

    private Algorithms() {
    }

    public static long factorialRecursive(int n) {
        if (n <= 1)
            return 1;
        return (n * factorialRecursive(n - 1)) % MOD;
    }

    public static long factorialIterative(int n) {
        long result = 1;
        for (int i = 2; i <= n; i++)
            result = (result * i) % MOD;
        return result;
    }

    public static List<Integer> treeRecursive(int[] values) {
        List<Integer> out = new ArrayList<>(values.length);
        treeVisit(values, 0, out);
        return out;
    }

    private static void treeVisit(int[] a, int i, List<Integer> out) {
        if (i >= a.length)
            return;
        treeVisit(a, 2 * i + 1, out);
        out.add(a[i]);
        treeVisit(a, 2 * i + 2, out);
    }

    public static List<Integer> treeIterative(int[] a) {
        List<Integer> out = new ArrayList<>(a.length);
        Deque<Integer> stack = new ArrayDeque<>();
        int i = 0;
        while (!stack.isEmpty() || i < a.length) {
            while (i < a.length) {
                stack.push(i);
                i = 2 * i + 1;
            }
            i = stack.pop();
            out.add(a[i]);
            i = 2 * i + 2;
        }
        return out;
    }

    private static int[] merge(int[] a, int[] b) {
        int[] out = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length) {
            out[k++] = a[i] <= b[j] ? a[i++] : b[j++];
        }
        while (i < a.length) {
            out[k++] = a[i++];
        }
        while (j < b.length) {
            out[k++] = b[j++];
        }
        return out;
    }

    public static int[] mergeRecursive(int[] a) {
        if (a.length <= 1)
            return a.clone();
        int mid = a.length / 2;
        return merge(mergeRecursive(Arrays.copyOfRange(a, 0, mid)),
                mergeRecursive(Arrays.copyOfRange(a, mid, a.length)));
    }

    public static int[] mergeIterative(int[] input) {
        int[] a = input.clone();
        record Frame(int start, int end, boolean childrenSorted) {
        }
        Deque<Frame> stack = new ArrayDeque<>();
        stack.push(new Frame(0, a.length, false));
        while (!stack.isEmpty()) {
            Frame frame = stack.pop();
            if (frame.end - frame.start <= 1)
                continue;
            int mid = (frame.start + frame.end) / 2;
            if (!frame.childrenSorted) {
                stack.push(new Frame(frame.start, frame.end, true));
                stack.push(new Frame(mid, frame.end, false));
                stack.push(new Frame(frame.start, mid, false));
                continue;
            }
            int[] left = Arrays.copyOfRange(a, frame.start, mid);
            int[] right = Arrays.copyOfRange(a, mid, frame.end);
            int[] merged = merge(left, right);
            System.arraycopy(merged, 0, a, frame.start, merged.length);
        }
        return a;
    }
}
