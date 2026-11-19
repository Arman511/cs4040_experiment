use csv::Reader;
use serde::Deserialize;
use std::{path::PathBuf, time::Instant};

const MOD: u64 = 1_000_000_007;
const WARMUPS: usize = 5;
const REPETITIONS: usize = 30;

#[derive(Deserialize)]
struct FactorialRow {
    n: usize,
}
#[derive(Deserialize)]
struct ArrayRow {
    size: Option<usize>,
    node_count: Option<usize>,
    values_json: String,
}

fn factorial_recursive(n: usize) -> u64 {
    if n <= 1 {
        1
    } else {
        (n as u64 * factorial_recursive(n - 1)) % MOD
    }
}
fn factorial_iterative(n: usize) -> u64 {
    (2..=n).fold(1u64, |acc, x| (acc * x as u64) % MOD)
}
fn tree_reccursive(a: &[i64], i: usize, out: &mut Vec<i64>) {
    if i >= a.len() {
        return;
    }
    tree_reccursive(a, 2 * i + 1, out);
    out.push(a[i]);
    tree_reccursive(a, 2 * i + 2, out);
}
fn tree_recursive(a: &[i64]) -> Vec<i64> {
    let mut out = Vec::with_capacity(a.len());
    tree_reccursive(a, 0, &mut out);
    out
}
fn tree_iterative(a: &[i64]) -> Vec<i64> {
    let mut out = Vec::with_capacity(a.len());
    let mut stack = Vec::new();
    let mut i = 0usize;
    while !stack.is_empty() || i < a.len() {
        while i < a.len() {
            stack.push(i);
            i = 2 * i + 1;
        }
        i = stack.pop().unwrap();
        out.push(a[i]);
        i = 2 * i + 2;
    }
    out
}
fn merge(a: &[i64], b: &[i64]) -> Vec<i64> {
    let (mut i, mut j) = (0, 0);
    let mut out = Vec::with_capacity(a.len() + b.len());
    while i < a.len() && j < b.len() {
        if a[i] <= b[j] {
            out.push(a[i]);
            i += 1;
        } else {
            out.push(b[j]);
            j += 1;
        }
    }
    out.extend_from_slice(&a[i..]);
    out.extend_from_slice(&b[j..]);
    out
}
fn merge_recursive(a: &[i64]) -> Vec<i64> {
    if a.len() <= 1 {
        return a.to_vec();
    }
    let mid = a.len() / 2;
    merge(&merge_recursive(&a[..mid]), &merge_recursive(&a[mid..]))
}
fn merge_iterative(a: &[i64]) -> Vec<i64> {
    let mut v = a.to_vec();
    let mut stack = vec![(0, v.len(), false)];
    while let Some((start, end, children_sorted)) = stack.pop() {
        if end - start <= 1 {
            continue;
        }
        let mid = (start + end) / 2;
        if !children_sorted {
            stack.push((start, end, true));
            stack.push((mid, end, false));
            stack.push((start, mid, false));
            continue;
        }
        let merged = merge(&v[start..mid], &v[mid..end]);
        v[start..end].copy_from_slice(&merged);
    }
    v
}

fn record(
    rows: &mut Vec<(String, String, String, usize, usize, u128)>,
    alg: &str,
    mode: &str,
    size: usize,
    rep: usize,
    ns: u128,
) {
    rows.push((String::from("rust"), alg.into(), mode.into(), size, rep, ns));
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 7 && args[1] == "--timing" {
        let raw_arg = &args[4];
        let raw = if let Some(path) = raw_arg.strip_prefix('@') {
            std::fs::read_to_string(path)?
        } else {
            raw_arg.clone()
        };
        let expected_raw = std::fs::read_to_string(&args[5])?;
        let repetitions: usize = args[6].parse()?;
        if repetitions == 0 {
            return Err("repetitions must be positive".into());
        }
        macro_rules! time_case {
            ($operation:expr, $expected:expr) => {{
                for _ in 0..WARMUPS {
                    std::hint::black_box($operation);
                }
                for _ in 0..repetitions {
                    let start = Instant::now();
                    let result = std::hint::black_box($operation);
                    let elapsed = start.elapsed().as_nanos();
                    if result != $expected {
                        return Err(format!("Incorrect result for {} {}", args[2], args[3]).into());
                    }
                    std::hint::black_box(result);
                    println!("{elapsed}");
                }
            }};
        }
        match (args[2].as_str(), args[3].as_str()) {
            ("factorial", mode @ ("recursive" | "iterative")) => {
                let n: usize = raw.parse()?;
                let expected: u64 = serde_json::from_str(&expected_raw)?;
                let f = if mode == "recursive" {
                    factorial_recursive
                } else {
                    factorial_iterative
                };
                time_case!(f(std::hint::black_box(n)), expected);
            }
            (algorithm @ ("tree" | "merge_sort"), mode @ ("recursive" | "iterative")) => {
                let values: Vec<i64> = serde_json::from_str(&raw)?;
                let expected: Vec<i64> = serde_json::from_str(&expected_raw)?;
                let f: fn(&[i64]) -> Vec<i64> = match (algorithm, mode) {
                    ("tree", "recursive") => tree_recursive,
                    ("tree", "iterative") => tree_iterative,
                    ("merge_sort", "recursive") => merge_recursive,
                    _ => merge_iterative,
                };
                time_case!(f(std::hint::black_box(&values)), expected);
            }
            _ => return Err("invalid --timing arguments".into()),
        }
        return Ok(());
    }
    if args.len() == 5 && args[1] == "--profile" {
        let algorithm = &args[2];
        let mode = &args[3];
        let raw_arg = &args[4];
        let raw_owned = if raw_arg.starts_with("@") {
            std::fs::read_to_string(&raw_arg[1..])?
        } else {
            raw_arg.clone()
        };
        let raw = raw_owned.as_str();
        match (algorithm.as_str(), mode.as_str()) {
            ("factorial", "recursive") => {
                std::hint::black_box(factorial_recursive(raw.parse()?));
            }
            ("factorial", "iterative") => {
                std::hint::black_box(factorial_iterative(raw.parse()?));
            }
            ("tree", "recursive") => {
                let a: Vec<i64> = serde_json::from_str(raw)?;
                std::hint::black_box(tree_recursive(&a));
            }
            ("tree", "iterative") => {
                let a: Vec<i64> = serde_json::from_str(raw)?;
                std::hint::black_box(tree_iterative(&a));
            }
            ("merge_sort", "recursive") => {
                let a: Vec<i64> = serde_json::from_str(raw)?;
                std::hint::black_box(merge_recursive(&a));
            }
            ("merge_sort", "iterative") => {
                let a: Vec<i64> = serde_json::from_str(raw)?;
                std::hint::black_box(merge_iterative(&a));
            }
            _ => return Err("invalid --profile arguments".into()),
        }
        return Ok(());
    }

    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    let data = root.join("test_data");
    let mut rows = Vec::new();

    let mut rdr = Reader::from_path(data.join("factorial.csv"))?;
    for row in rdr.deserialize::<FactorialRow>() {
        let n = row?.n;
        for (mode, f) in [
            ("recursive", factorial_recursive as fn(usize) -> u64),
            ("iterative", factorial_iterative),
        ] {
            let expected = f(n);
            for _ in 0..WARMUPS {
                std::hint::black_box(f(n));
            }
            for rep in 1..=REPETITIONS {
                let t = Instant::now();
                let got = std::hint::black_box(f(n));
                let ns = t.elapsed().as_nanos();
                assert_eq!(got, expected);
                record(&mut rows, "factorial", mode, n, rep, ns);
            }
        }
    }

    let mut rdr = Reader::from_path(data.join("tree.csv"))?;
    for row in rdr.deserialize::<ArrayRow>() {
        let r = row?;
        let size = r.node_count.unwrap();
        let a: Vec<i64> = serde_json::from_str(&r.values_json)?;
        for (mode, f) in [
            ("recursive", tree_recursive as fn(&[i64]) -> Vec<i64>),
            ("iterative", tree_iterative),
        ] {
            let expected = f(&a);
            for _ in 0..WARMUPS {
                std::hint::black_box(f(&a));
            }
            for rep in 1..=REPETITIONS {
                let t = Instant::now();
                let got = std::hint::black_box(f(&a));
                let ns = t.elapsed().as_nanos();
                assert_eq!(got, expected);
                record(&mut rows, "tree", mode, size, rep, ns);
            }
        }
    }

    let mut rdr = Reader::from_path(data.join("merge_sort.csv"))?;
    for row in rdr.deserialize::<ArrayRow>() {
        let r = row?;
        let size = r.size.unwrap();
        let a: Vec<i64> = serde_json::from_str(&r.values_json)?;
        for (mode, f) in [
            ("recursive", merge_recursive as fn(&[i64]) -> Vec<i64>),
            ("iterative", merge_iterative),
        ] {
            let expected = f(&a);
            for _ in 0..WARMUPS {
                std::hint::black_box(f(&a));
            }
            for rep in 1..=REPETITIONS {
                let t = Instant::now();
                let got = std::hint::black_box(f(&a));
                let ns = t.elapsed().as_nanos();
                assert_eq!(got, expected);
                record(&mut rows, "merge_sort", mode, size, rep, ns);
            }
        }
    }

    let out = root.join("results/rust_execution_times.csv");
    std::fs::create_dir_all(root.join("results"))?;
    let mut w = csv::Writer::from_path(&out)?;
    w.write_record([
        "language",
        "algorithm",
        "mode",
        "input_size",
        "repetition",
        "elapsed_ns",
    ])?;
    for (lang, alg, mode, size, rep, ns) in rows {
        w.write_record([
            lang,
            alg,
            mode,
            size.to_string(),
            rep.to_string(),
            ns.to_string(),
        ])?;
    }
    w.flush()?;
    println!("Raw measurements: {}", out.display());
    Ok(())
}
