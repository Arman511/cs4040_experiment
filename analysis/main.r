library(dplyr)
library(ggplot2)
source("analysis/functions.R")

time_data <- read.csv("results/time_usage.csv")
memory_data <- read.csv("results/memory_usage.csv")
snapshots <- read.csv("results/memory_snapshots.csv")

time_data <- mutate(time_data, elapsed_ms = execution_time_ns / 1e6)
memory_data <- mutate(memory_data, peak_mib = peak_memory_bytes / 1024^2)

for (directory in c("analysis/tables", "analysis/figures")) {
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
}

time_summary <- summarise_measurements(time_data, "elapsed_ms") |>
  rename(median_ms = median, iqr_ms = iqr, q1_ms = q1, q3_ms = q3)
memory_summary <- summarise_measurements(memory_data, "peak_mib") |>
  rename(median_mib = median, iqr_mib = iqr, q1_mib = q1, q3_mib = q3)

snapshot_runs <- snapshots |>
  arrange(language, algorithm, mode, input_size, repetition, time, snapshot) |>
  group_by(language, algorithm, mode, input_size, repetition)

snapshot_run_means <- snapshot_runs |>
  summarise(
    mean_mib = sum(
      diff(time) * (head(total_bytes, -1) + tail(total_bytes, -1)) / 2
    ) /
      (last(time) - first(time)) / 1024^2,
    .groups = "drop"
  )

snapshot_summary <- summarise_measurements(snapshot_run_means, "mean_mib") |>
  rename(median_mib = median, iqr_mib = iqr, q1_mib = q1, q3_mib = q3)

progress_grid <- seq(0, 100, by = 1)

snapshot_curves <- snapshot_runs |>
  group_modify(~ tibble(
    progress_percent = progress_grid,
    memory_mib = approx(
      x = (.x$time - first(.x$time)) / (last(.x$time) - first(.x$time)) * 100,
      y = .x$total_bytes / 1024^2,
      xout = progress_grid, method = "linear", rule = 2
    )$y
  )) |>
  ungroup() |>
  group_by(language, algorithm, mode, input_size, progress_percent) |>
  summarise(
    n = n(),
    median_mib = median(memory_mib),
    q1_mib = unname(quantile(memory_mib, 0.25)),
    q3_mib = unname(quantile(memory_mib, 0.75)),
    .groups = "drop"
  )

maximum_time_table <- time_summary |>
  group_by(algorithm) |>
  filter(input_size == max(input_size)) |>
  ungroup() |>
  transmute(
    Algorithm = recode(
      algorithm,
      merge_sort = "Merge sort",
      tree = "Tree",
      factorial = "Factorial"
    ),
    Mode = recode(mode, iterative = "Iterative", recursive = "Recursive"),
    Language = recode(language, java = "Java", python = "Python", rust = "Rust"),
    Median = vapply(median_ms, format_number, character(1))
  ) |>
  tidyr::pivot_wider(names_from = Language, values_from = Median) |>
  mutate(
    Algorithm = factor(Algorithm, levels = c("Merge sort", "Tree", "Factorial")),
    Mode = factor(Mode, levels = c("Iterative", "Recursive"))
  ) |>
  arrange(Algorithm, Mode) |>
  transmute(
    Algorithm = as.character(Algorithm),
    Mode = as.character(Mode),
    Java, Python, Rust
  )

maximum_time_latex <- knitr::kable(
  maximum_time_table,
  format = "latex",
  booktabs = TRUE,
  caption = "Median execution time at maximum input sizes (ms).",
  label = "execution_time_results",
  align = c("l", "l", "r", "r", "r"),
  escape = TRUE
)
writeLines(
  as.character(maximum_time_latex),
  "analysis/tables/execution_time_results.tex"
)

memory_tests <- compare_by_group(memory_data, "peak_memory_bytes") |>
  mutate(p_holm = p.adjust(p_value, method = "holm"))

snapshot_tests <- compare_by_group(snapshot_run_means, "mean_mib") |>
  mutate(p_holm = p.adjust(p_value, method = "holm"))

time_ratios <- compare_by_group(time_data, "elapsed_ms")

write.csv(
  memory_tests,
  "analysis/tables/h1_memory_tests.csv",
  row.names = FALSE
)

write.csv(
  snapshot_tests,
  "analysis/tables/h1_snapshot_tests.csv",
  row.names = FALSE
)

algorithm_interactions <- time_data |>
  group_by(algorithm) |>
  group_modify(~ interaction_test(.x)) |>
  ungroup() |>
  mutate(p_holm = p.adjust(p_value, method = "holm"))

overall_reduced <- lm(
  log(elapsed_ms) ~ factor(input_size) + algorithm * language +
    algorithm * mode + factor(input_size):mode,
  data = time_data
)
overall_full <- update(overall_reduced, . ~ . + language:mode)
overall_result <- anova(overall_reduced, overall_full)
overall_interaction <- tibble(
  df = overall_result$Df[[2]],
  residual_df = overall_result$Res.Df[[2]],
  statistic = overall_result$F[[2]],
  p_value = overall_result$`Pr(>F)`[[2]]
)
write.csv(
  algorithm_interactions,
  "analysis/tables/h2_language_mode_tests.csv",
  row.names = FALSE
)
write.csv(
  overall_interaction,
  "analysis/tables/h2_overall_test.csv",
  row.names = FALSE
)

algorithm_labels <- c(
  factorial = "Factorial",
  merge_sort = "Merge sort",
  tree = "Tree"
)
language_labels <- c(java = "Java", python = "Python", rust = "Rust")
mode_colors <- setNames(c("#2878B5", "#D45D00"), c("iterative", "recursive"))
language_colors <- c(java = "#2878B5", python = "#D45D00", rust = "#24804A")

ggsave(
  "analysis/figures/time_distributions.pdf",
  distribution_plot(
    time_summary, "median_ms", "q1_ms", "q3_ms",
    "Execution time by input size", "Median elapsed time (ms)"
  ),
  width = 11, height = 8
)
ggsave(
  "analysis/figures/memory_distributions.pdf",
  distribution_plot(
    memory_summary, "median_mib", "q1_mib", "q3_mib",
    "Peak process memory by input size", "Median peak memory (MiB)"
  ),
  width = 11, height = 8
)
ggsave(
  "analysis/figures/time_relative_ratios.pdf",
  ratio_plot(
    time_ratios,
    "Relative execution time",
    subtitle = "Ratio > 1 means recursive is slower (iterative is faster)"
  ),
  width = 11, height = 5
)

ggsave(
  "analysis/figures/memory_relative_ratios.pdf",
  ratio_plot(
    memory_tests,
    "Relative peak memory",
    subtitle = "Ratio > 1 means recursive uses more memory (iterative uses less)"
  ),
  width = 11, height = 5
)

ggsave(
  "analysis/figures/memory_snapshot_average_ratios.pdf",
  ratio_plot(
    snapshot_tests,
    "Relative time-weighted average memory",
    subtitle = "Ratio > 1 means recursive uses more memory (iterative uses less)"
  ),
  width = 11, height = 5
)

snapshot_pages <- distinct(
  snapshot_curves,
  algorithm,
  input_size
) |>
  arrange(algorithm, input_size)

for (i in seq_len(nrow(snapshot_pages))) {
  algorithm <- snapshot_pages$algorithm[[i]]
  input_size <- snapshot_pages$input_size[[i]]
  ggsave(
    sprintf(
      "analysis/figures/memory_over_time_%s_%s.pdf",
      algorithm,
      input_size
    ),
    snapshot_plot(snapshot_curves, algorithm, input_size),
    width = 11,
    height = 5
  )
}

cat("\nH1: recursive peak memory > iterative (one-sided; Holm-adjusted):\n")
print(as.data.frame(select(
  memory_tests, language, algorithm, input_size,
  ratio_recursive_to_iterative, p_holm
)), row.names = FALSE, digits = 4)
cat("\nH1: time-weighted average memory (one-sided; Holm-adjusted):\n")
print(as.data.frame(select(
  snapshot_tests, language, algorithm, input_size,
  ratio_recursive_to_iterative, p_holm
)), row.names = FALSE, digits = 4)
cat("\nH2: language-by-mode interaction by algorithm (Holm-adjusted):\n")
print(as.data.frame(algorithm_interactions), row.names = FALSE, digits = 4)
cat("\nH2: overall language-by-mode interaction:\n")
print(as.data.frame(overall_interaction), row.names = FALSE, digits = 4)
