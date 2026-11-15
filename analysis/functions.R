library(dplyr)
library(ggplot2)

text_size <- 20

summarise_measurements <- function(data, metric) {
  data |>
    group_by(language, algorithm, mode, input_size) |>
    summarise(
      n = n(),
      median = median(.data[[metric]]),
      iqr = IQR(.data[[metric]]),
      q1 = unname(quantile(.data[[metric]], 0.25)),
      q3 = unname(quantile(.data[[metric]], 0.75)),
      .groups = "drop"
    )
}
format_number <- function(value) {
  if (is.na(value)) {
    return("not estimable")
  }
  if (value != 0 && abs(value) < 0.001) {
    return(format(signif(value, 3), scientific = TRUE, trim = TRUE))
  }
  format(signif(value, 3), scientific = FALSE, trim = TRUE)
}

format_interval <- function(lower, upper) {
  if (is.na(lower) || is.na(upper)) {
    return("not estimable")
  }
  paste(format_number(lower), format_number(upper), sep = "--")
}

write_latex_table <- function(data, caption, label, file) {
  table <- knitr::kable(
    data,
    format = "latex",
    booktabs = TRUE,
    longtable = TRUE,
    caption = caption,
    label = label,
    align = c("l", rep("r", ncol(data) - 1)),
    escape = TRUE
  )
  writeLines(as.character(table), file)
}

configuration <- function(language, algorithm, mode = NULL) {
  paste(tools::toTitleCase(language), gsub("_", " ", algorithm), mode)
}
compare_modes <- function(data, metric) {
  iterative <- log(data[[metric]][data$mode == "iterative"])
  recursive <- log(data[[metric]][data$mode == "recursive"])
  difference <- mean(recursive) - mean(iterative)

  if (var(iterative) == 0 && var(recursive) == 0) {
    return(tibble(
      n_iterative = length(iterative),
      n_recursive = length(recursive),
      ratio_recursive_to_iterative = exp(difference),
      ratio_ci_lower = NA_real_,
      ratio_ci_upper = NA_real_,
      p_value = NA_real_,
      p_two_sided = NA_real_,
      zero_variance = TRUE,
      test_method = "not estimable (zero variance)"
    ))
  }

  two_sided <- t.test(recursive, iterative)
  greater <- t.test(recursive, iterative, alternative = "greater")
  tibble(
    n_iterative = length(iterative),
    n_recursive = length(recursive),
    ratio_recursive_to_iterative = exp(difference),
    ratio_ci_lower = exp(two_sided$conf.int[[1]]),
    ratio_ci_upper = exp(two_sided$conf.int[[2]]),
    p_value = greater$p.value,
    p_two_sided = two_sided$p.value,
    zero_variance = FALSE,
    test_method = "Welch t-test"
  )
}

compare_by_group <- function(data, metric) {
  data |>
    group_by(language, algorithm, input_size) |>
    group_modify(~ compare_modes(.x, metric)) |>
    ungroup()
}
interaction_test <- function(data) {
  data$input_size <- factor(data$input_size)
  reduced <- lm(log(elapsed_ms) ~ input_size * mode + language, data = data)
  full <- update(reduced, . ~ . + language:mode)
  result <- anova(reduced, full)
  tibble(
    df = result$Df[[2]],
    statistic = result$F[[2]],
    p_value = result$`Pr(>F)`[[2]]
  )
}
ratio_plot <- function(data, title, subtitle = "Recursive / iterative ratio (> 1 means iterative uses fewer resources)") {
  data <- data |>
    mutate(
      algorithm = factor(algorithm,
        levels = names(algorithm_labels),
        labels = algorithm_labels
      )
    )
  intervals <- filter(data, is.finite(ratio_ci_lower), is.finite(ratio_ci_upper))
  line_data <- data |>
    group_by(algorithm, language) |>
    filter(n() > 1) |>
    ungroup()
  ggplot(data, aes(
    x = input_size, y = ratio_recursive_to_iterative,
    color = language
  )) +
    geom_hline(
      aes(yintercept = 1, linetype = "Equal values (ratio = 1)"),
      color = "grey50"
    ) +
    geom_line(data = line_data, linewidth = 0.5) +
    geom_point(size = 1.7) +
    geom_linerange(
      data = intervals, aes(ymin = ratio_ci_lower, ymax = ratio_ci_upper),
      linewidth = 0.5
    ) +
    facet_wrap(~algorithm, scales = "free") +
    scale_x_log10() +
    scale_y_log10() +
    scale_color_manual(
      values = language_colors, labels = language_labels,
      name = "Language"
    ) +
    scale_linetype_manual(
      values = c("Equal values (ratio = 1)" = "dashed"),
      name = "Reference"
    ) +
    labs(
      title = title,
      subtitle = subtitle,
      x = "Input size",
      y = "Recursive / iterative mean ratio",
      caption = paste(
        "Bars show 95% confidence intervals; absent bars indicate",
        "intervals could not be estimated."
      )
    ) +
    theme_minimal(base_size = text_size) +
    theme(legend.position = "bottom")
}
snapshot_plot <- function(data, algorithm_name, size) {
  data <- data |>
    filter(algorithm == algorithm_name, input_size == size) |>
    mutate(language = factor(language,
      levels = names(language_labels), labels = language_labels
    ))
  ggplot(data, aes(x = progress_percent, y = median_mib, color = mode, fill = mode)) +
    geom_ribbon(aes(ymin = q1_mib, ymax = q3_mib), alpha = 0.18, color = NA) +
    geom_line(linewidth = 0.7) +
    facet_wrap(~language, scales = "free_y") +
    scale_color_manual(
      values = mode_colors,
      breaks = c("iterative", "recursive"),
      labels = c("Iterative", "Recursive"),
      name = "Implementation"
    ) +
    scale_fill_manual(
      values = mode_colors,
      breaks = c("iterative", "recursive"),
      labels = c("Iterative", "Recursive"),
      name = "Implementation"
    ) +
    scale_x_continuous(limits = c(0, 100), breaks = seq(0, 100, 25)) +
    labs(
      title = paste(algorithm_labels[[algorithm_name]], "memory profile; input size", size),
      x = "Elapsed time (%)",
      y = "Profiled process memory (MiB)"
    ) +
    theme_minimal(base_size = text_size) +
    theme(legend.position = "bottom")
}
distribution_plot <- function(summary, median_column, q1_column, q3_column,
                              title, y_label) {
  data <- summary |>
    mutate(
      algorithm = factor(algorithm,
        levels = names(algorithm_labels),
        labels = algorithm_labels
      ),
      language = factor(language,
        levels = names(language_labels),
        labels = language_labels
      )
    )
  line_data <- data |>
    group_by(algorithm, language, mode) |>
    filter(n() > 1) |>
    ungroup()
  ggplot(data, aes(x = input_size, y = .data[[median_column]], color = mode)) +
    geom_line(data = line_data, linewidth = 0.5) +
    geom_linerange(
      aes(ymin = .data[[q1_column]], ymax = .data[[q3_column]]),
      linewidth = 0.5
    ) +
    geom_point(size = 1.5) +
    facet_grid(language ~ algorithm, scales = "free") +
    scale_x_log10() +
    scale_y_log10() +
    scale_color_manual(
      values = mode_colors,
      breaks = c("iterative", "recursive"),
      labels = c("Iterative", "Recursive"),
      name = "Implementation"
    ) +
    labs(
      title = title, x = "Input size", y = y_label
    ) +
    theme_minimal(base_size = text_size) +
    theme(legend.position = "bottom")
}
