package benchmark;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.management.CompilationMXBean;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.function.Supplier;
import tools.jackson.databind.ObjectMapper;

public final class TimeOne {
    @SuppressWarnings("unused")
    private static volatile Object _sink;

    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            throw new IllegalArgumentException("Usage: TimeOne algorithm mode input answer_file");
        }
        String raw = args[2].startsWith("@")
                ? Files.readString(Path.of(args[2].substring(1)))
                : args[2];
        ObjectMapper mapper = new ObjectMapper();
        String answer = Files.readString(Path.of(args[3]));
        Object expected;
        if (args[0].equals("factorial")) {
            expected = mapper.readValue(answer, Long.class);
        } else {
            int[] expectedArray = mapper.readValue(answer, int[].class);
            expected = args[0].equals("tree") ? Arrays.stream(expectedArray).boxed().toList() : expectedArray;
        }
        Supplier<Object> operation;
        if (args[0].equals("factorial")) {
            int n = Integer.parseInt(raw);
            operation = switch (args[1]) {
                case "recursive" -> () -> Algorithms.factorialRecursive(n);
                case "iterative" -> () -> Algorithms.factorialIterative(n);
                default -> throw new IllegalArgumentException("Unknown mode");
            };
        } else {
            int[] values = mapper.readValue(raw, int[].class);
            operation = switch (args[0] + ":" + args[1]) {
                case "tree:recursive" -> () -> Algorithms.treeRecursive(values);
                case "tree:iterative" -> () -> Algorithms.treeIterative(values);
                case "merge_sort:recursive" -> () -> Algorithms.mergeRecursive(values);
                case "merge_sort:iterative" -> () -> Algorithms.mergeIterative(values);
                default -> throw new IllegalArgumentException("Unknown algorithm/mode");
            };
        }

        CompilationMXBean compiler = ManagementFactory.getCompilationMXBean();
        if (compiler == null || !compiler.isCompilationTimeMonitoringSupported()) {
            throw new IllegalStateException("JVM compilation-time monitoring is unavailable");
        }
        try (BufferedReader input = new BufferedReader(new InputStreamReader(System.in))) {
            String line;
            while ((line = input.readLine()) != null) {
                String[] parts = line.split(" ");
                if (parts.length != 2 || !(parts[0].equals("warmup") || parts[0].equals("measure"))) {
                    throw new IllegalArgumentException("Expected 'warmup' | 'measure'");
                }
                int count = Integer.parseInt(parts[1]);
                if (count < 1) {
                    throw new IllegalArgumentException("Count must be positive");
                }
                long compilationBefore = compiler.getTotalCompilationTime();
                long total = 0;
                StringBuilder measurements = new StringBuilder();
                for (int i = 0; i < count; i++) {
                    long start = System.nanoTime();
                    Object result = operation.get();
                    long elapsed = System.nanoTime() - start;
                    _sink = result;
                    total += elapsed;
                    if (parts[0].equals("measure")) {
                        boolean correct = expected instanceof int[] expectedArray
                                ? result instanceof int[] resultArray && Arrays.equals(resultArray, expectedArray)
                                : expected.equals(result);
                        if (!correct) {
                            throw new IllegalStateException("Incorrect result for " + args[0] + " " + args[1]);
                        }
                        if (i > 0)
                            measurements.append(',');
                        measurements.append(elapsed);
                    }
                }
                if (parts[0].equals("warmup")) {
                    System.out.println(total + " " + compiler.getTotalCompilationTime()
                            + " " + compilationBefore);
                } else {
                    System.out.println(measurements);
                }
                System.out.flush();
            }
        }
    }
}
