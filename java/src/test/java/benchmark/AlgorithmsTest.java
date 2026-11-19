package benchmark;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.Reader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVRecord;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class AlgorithmsTest {
    private static final long MOD = 1_000_000_007L;
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Path DATA = Path.of(System.getProperty("user.dir"))
            .getParent()
            .resolve("test_data");

    @Test
    void factorialMatchesReferenceForEdgesRandomAndDatasets() throws Exception {
        assertEquals(1, Algorithms.factorialRecursive(0));
        assertEquals(1, Algorithms.factorialIterative(0));
        assertEquals(1, Algorithms.factorialRecursive(1));
        assertEquals(1, Algorithms.factorialIterative(1));

        Random random = new Random(2026);
        for (int i = 0; i < 100; i++) {
            int n = random.nextInt(801);
            long expected = factorialReference(n);
            assertEquals(expected, Algorithms.factorialRecursive(n));
            assertEquals(expected, Algorithms.factorialIterative(n));
        }

        List<CSVRecord> inputs = records("factorial.csv");
        List<CSVRecord> answers = records("ans_factorial.csv");
        assertEquals(inputs.size(), answers.size());
        for (int i = 0; i < inputs.size(); i++) {
            int n = Integer.parseInt(inputs.get(i).get("n"));
            assertEquals(inputs.get(i).get("n"), answers.get(i).get("n"));
            long expected = MAPPER.readValue(answers.get(i).get("result_json"), Long.class);
            assertEquals(expected, Algorithms.factorialRecursive(n));
            assertEquals(expected, Algorithms.factorialIterative(n));
        }
        assertEquals("800", inputs.getLast().get("n"));
    }

    @Test
    void treeMatchesReferenceForEdgesRandomAndDatasets() throws Exception {
        assertTree(new int[0]);
        assertTree(new int[] { 1 });
        assertTree(new int[] { 4, 2, 6, 1, 3, 5, 7 });

        Random random = new Random(2026);
        for (int size : new int[] { 3, 17, 128, 1024 }) {
            int[] values = random.ints(size, -10_000, 10_001).toArray();
            assertTree(values);
        }

        List<CSVRecord> inputs = records("tree.csv");
        List<CSVRecord> answers = records("ans_tree.csv");
        assertEquals(inputs.size(), answers.size());
        for (int i = 0; i < inputs.size(); i++) {
            assertEquals(inputs.get(i).get("node_count"), answers.get(i).get("node_count"));
            int[] values = MAPPER.readValue(inputs.get(i).get("values_json"), int[].class);
            int[] expected = MAPPER.readValue(answers.get(i).get("result_json"), int[].class);
            assertEquals(Arrays.stream(expected).boxed().toList(), Algorithms.treeRecursive(values));
            assertEquals(Arrays.stream(expected).boxed().toList(), Algorithms.treeIterative(values));
        }
        assertEquals("50000", inputs.getLast().get("node_count"));
    }

    @Test
    void mergeSortMatchesReferenceForEdgesRandomAndDatasets() throws Exception {
        assertMerge(new int[0]);
        assertMerge(new int[] { 1 });
        assertMerge(new int[] { 2, 1 });
        assertMerge(new int[] { 5, -1, 5, 3, 0 });

        Random random = new Random(2026);
        for (int size : new int[] { 3, 17, 128, 1024 }) {
            assertMerge(random.ints(size, -10_000, 10_001).toArray());
        }

        List<CSVRecord> inputs = records("merge_sort.csv");
        List<CSVRecord> answers = records("ans_merge_sort.csv");
        assertEquals(inputs.size(), answers.size());
        for (int i = 0; i < inputs.size(); i++) {
            assertEquals(inputs.get(i).get("size"), answers.get(i).get("size"));
            int[] values = MAPPER.readValue(inputs.get(i).get("values_json"), int[].class);
            int[] expected = MAPPER.readValue(answers.get(i).get("result_json"), int[].class);
            assertArrayEquals(expected, Algorithms.mergeRecursive(values));
            assertArrayEquals(expected, Algorithms.mergeIterative(values));
        }
        assertEquals("50000", inputs.getLast().get("size"));
    }

    private static void assertTree(int[] values) {
        List<Integer> expected = new ArrayList<>();
        visit(values, 0, expected);
        assertEquals(expected, Algorithms.treeRecursive(values));
        assertEquals(expected, Algorithms.treeIterative(values));
    }

    private static void visit(int[] values, int index, List<Integer> output) {
        if (index >= values.length)
            return;
        visit(values, 2 * index + 1, output);
        output.add(values[index]);
        visit(values, 2 * index + 2, output);
    }

    private static void assertMerge(int[] values) {
        int[] expected = values.clone();
        Arrays.sort(expected);
        assertArrayEquals(expected, Algorithms.mergeRecursive(values));
        assertArrayEquals(expected, Algorithms.mergeIterative(values));
    }

    private static long factorialReference(int n) {
        long result = 1;
        for (int i = 2; i <= n; i++)
            result = result * i % MOD;
        return result;
    }

    private static List<CSVRecord> records(String name) throws Exception {
        try (Reader reader = Files.newBufferedReader(DATA.resolve(name))) {
            return CSVFormat.DEFAULT.builder()
                    .setHeader()
                    .setSkipHeaderRecord(true)
                    .build()
                    .parse(reader)
                    .getRecords();
        }
    }
}
