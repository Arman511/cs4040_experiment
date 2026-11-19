#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn factorial_matches_reference_for_edges_random_and_datasets() {
        for n in [0, 1, 2, 10, 250] {
            let expected = factorial_reference(n);
            assert_eq!(factorial_recursive(n), expected);
            assert_eq!(factorial_iterative(n), expected);
        }
        let mut state = 2026u64;
        for _ in 0..100 {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let n = (state % 801) as usize;
            let expected = factorial_reference(n);
            assert_eq!(factorial_recursive(n), expected);
            assert_eq!(factorial_iterative(n), expected);
        }

        let inputs: Vec<FactorialRow> = read_csv("factorial.csv");
        let answers: Vec<(usize, u64)> = read_csv_rows("ans_factorial.csv")
            .into_iter()
            .map(|row| {
                let n = row[0].parse().unwrap();
                let result = row[1].parse().unwrap();
                (n, result)
            })
            .collect();
        assert_eq!(inputs.len(), answers.len());
        for (input, (answer_n, expected)) in inputs.iter().zip(answers) {
            assert_eq!(input.n, answer_n);
            assert_eq!(factorial_recursive(input.n), expected);
            assert_eq!(factorial_iterative(input.n), expected);
        }
        assert_eq!(inputs.last().unwrap().n, 800);
    }

    #[test]
    fn tree_matches_reference_for_edges_random_and_datasets() {
        for values in [vec![], vec![1], vec![4, 2, 6, 1, 3, 5, 7]] {
            let expected = tree_reference(&values);
            assert_eq!(tree_recursive(&values), expected);
            assert_eq!(tree_iterative(&values), expected);
        }
        for size in [3, 17, 128, 1024] {
            assert_tree(random_values(size));
        }

        let inputs: Vec<ArrayRow> = read_csv("tree.csv");
        let answers = read_csv_rows("ans_tree.csv");
        assert_eq!(inputs.len(), answers.len());
        for (input, answer) in inputs.iter().zip(answers) {
            assert_eq!(input.node_count.unwrap().to_string(), answer[0]);
            let values: Vec<i64> = serde_json::from_str(&input.values_json).unwrap();
            let expected: Vec<i64> = serde_json::from_str(&answer[1]).unwrap();
            assert_eq!(tree_recursive(&values), expected);
            assert_eq!(tree_iterative(&values), expected);
        }
        assert_eq!(inputs.last().unwrap().node_count, Some(50_000));
    }

    #[test]
    fn merge_sort_matches_reference_for_edges_random_and_datasets() {
        for values in [vec![], vec![1], vec![2, 1], vec![5, -1, 5, 3, 0]] {
            let mut expected = values.clone();
            expected.sort();
            assert_eq!(merge_recursive(&values), expected);
            assert_eq!(merge_iterative(&values), expected);
        }
        for size in [3, 17, 128, 1024] {
            let values = random_values(size);
            let mut expected = values.clone();
            expected.sort();
            assert_eq!(merge_recursive(&values), expected);
            assert_eq!(merge_iterative(&values), expected);
        }

        let inputs: Vec<ArrayRow> = read_csv("merge_sort.csv");
        let answers = read_csv_rows("ans_merge_sort.csv");
        assert_eq!(inputs.len(), answers.len());
        for (input, answer) in inputs.iter().zip(answers) {
            assert_eq!(input.size.unwrap().to_string(), answer[0]);
            let values: Vec<i64> = serde_json::from_str(&input.values_json).unwrap();
            let expected: Vec<i64> = serde_json::from_str(&answer[1]).unwrap();
            assert_eq!(merge_recursive(&values), expected);
            assert_eq!(merge_iterative(&values), expected);
        }
        assert_eq!(inputs.last().unwrap().size, Some(50_000));
    }

    fn factorial_reference(n: usize) -> u64 {
        (2..=n).fold(1, |result, factor| result * factor as u64 % MOD)
    }

    fn tree_reference(values: &[i64]) -> Vec<i64> {
        fn visit(values: &[i64], index: usize, output: &mut Vec<i64>) {
            if index >= values.len() {
                return;
            }
            visit(values, 2 * index + 1, output);
            output.push(values[index]);
            visit(values, 2 * index + 2, output);
        }
        let mut output = Vec::with_capacity(values.len());
        visit(values, 0, &mut output);
        output
    }

    fn assert_tree(values: Vec<i64>) {
        let expected = tree_reference(&values);
        assert_eq!(tree_recursive(&values), expected);
        assert_eq!(tree_iterative(&values), expected);
    }

    fn random_values(size: usize) -> Vec<i64> {
        let mut state = 2026u64;
        (0..size)
            .map(|_| {
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
                (state % 20_001) as i64 - 10_000
            })
            .collect()
    }

    fn data_dir() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("test_data")
    }

    fn read_csv<T: for<'de> Deserialize<'de>>(name: &str) -> Vec<T> {
        let mut reader = Reader::from_path(data_dir().join(name)).unwrap();
        reader.deserialize().map(Result::unwrap).collect()
    }

    fn read_csv_rows(name: &str) -> Vec<Vec<String>> {
        Reader::from_path(data_dir().join(name))
            .unwrap()
            .records()
            .map(|row| row.unwrap().iter().map(str::to_owned).collect())
            .collect()
    }
}
