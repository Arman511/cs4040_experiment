package benchmark;

import tools.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ProfileOne {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: ProfileOne algorithm mode input");
        }
        String algorithm = args[0], mode = args[1], raw = args[2];
        if (raw.startsWith("@")) {
            raw = Files.readString(Path.of(raw.substring(1)));
        }
        ObjectMapper mapper = new ObjectMapper();

        switch (algorithm + ":" + mode) {
            case "factorial:recursive" -> Algorithms.factorialRecursive(Integer.parseInt(raw));
            case "factorial:iterative" -> Algorithms.factorialIterative(Integer.parseInt(raw));
            case "tree:recursive" -> Algorithms.treeRecursive(mapper.readValue(raw, int[].class));
            case "tree:iterative" -> Algorithms.treeIterative(mapper.readValue(raw, int[].class));
            case "merge_sort:recursive" -> Algorithms.mergeRecursive(mapper.readValue(raw, int[].class));
            case "merge_sort:iterative" -> Algorithms.mergeIterative(mapper.readValue(raw, int[].class));
            default -> throw new IllegalArgumentException("Unknown algorithm/mode");
        }
    }
}
