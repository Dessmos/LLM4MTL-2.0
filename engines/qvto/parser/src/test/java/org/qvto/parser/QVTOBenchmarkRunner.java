package org.qvto.parser;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Stream;

public class QVTOBenchmarkRunner {

    private static final Path RESOURCE_DIR = Paths.get("src/test/resources/transformation");
    private static final Path REFERENCE_DIR = RESOURCE_DIR.resolve("reference");
    private static final String[] MODELS = {"claude-sonnet-4", "gemini-2-5-pro", "gpt-5"};
    private static final int CHRF_MAX_N = 6;
    private static final double CHRF_BETA = 2.0;

    @Test
    void generateBenchmarkCSV() throws IOException {
        List<String[]> results = new ArrayList<>();

        for (String model : MODELS) {
            Path modelDir = RESOURCE_DIR.resolve(model);
            if (!Files.isDirectory(modelDir)) {
                System.err.println("Model directory not found: " + modelDir);
                continue;
            }

            try (Stream<Path> paths = Files.walk(modelDir)) {
                List<Path> qvtoFiles = paths
                        .filter(p -> p.toString().endsWith(".qvto"))
                        .sorted()
                        .toList();

                for (Path qvtoFile : qvtoFiles) {
                    Path relativePath = modelDir.relativize(qvtoFile);
                    String fileName = qvtoFile.getFileName().toString();
                    String strategy = relativePath.getParent().toString().replace("\\", "/");

                    // Parse the file and get problem count
                    QVTOParserFacade facade = new QVTOParserFacade();
                    int problemCount;
                    boolean parseSuccess;
                    try {
                        String source = Files.readString(qvtoFile);
                        facade.parse(source);
                        problemCount = facade.getProblemCount();
                        parseSuccess = (problemCount == 0);
                    } catch (Exception e) {
                        problemCount = -1;
                        parseSuccess = false;
                    }

                    // Compute chrF against reference
                    double chrfScore = 0.0;
                    Path refFile = REFERENCE_DIR.resolve(fileName);
                    if (Files.exists(refFile)) {
                        String hypothesis = Files.readString(qvtoFile);
                        String reference = Files.readString(refFile);
                        chrfScore = computeChrF(hypothesis, reference);
                    }

                    results.add(new String[]{
                            model, strategy, fileName,
                            String.valueOf(problemCount),
                            String.valueOf(parseSuccess),
                            String.format(Locale.US, "%.4f", chrfScore)
                    });
                }
            }
        }

        // Write detailed CSV
        Path detailedCsvPath = Paths.get("benchmark_results_detailed.csv");
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(detailedCsvPath))) {
            pw.println("model,strategy,file,problem_count,parse_success,chrF");
            for (String[] row : results) {
                pw.println(String.join(",", row));
            }
        }

        // Aggregate by model/strategy for summary
        Map<String, List<String[]>> grouped = new LinkedHashMap<>();
        for (String[] row : results) {
            String key = row[0] + "," + row[1];
            grouped.computeIfAbsent(key, k -> new ArrayList<>()).add(row);
        }

        // Write summary CSV
        Path summaryCsvPath = Paths.get("benchmark_results_summary.csv");
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(summaryCsvPath))) {
            pw.println("model,strategy,total_files,parsed_ok,parse_rate,avg_problem_count,avg_chrF");
            for (var entry : grouped.entrySet()) {
                List<String[]> rows = entry.getValue();
                int totalFiles = rows.size();
                long parsedOk = rows.stream().filter(r -> Boolean.parseBoolean(r[4])).count();
                double parseRate = (double) parsedOk / totalFiles * 100.0;
                double avgProblems = rows.stream()
                        .mapToInt(r -> Math.max(0, Integer.parseInt(r[3])))
                        .average().orElse(0);
                double avgChrF = rows.stream()
                        .mapToDouble(r -> Double.parseDouble(r[5]))
                        .average().orElse(0);

                pw.printf(Locale.US, "%s,%d,%d,%.1f,%.2f,%.4f%n",
                        entry.getKey(), totalFiles, parsedOk, parseRate, avgProblems, avgChrF);
            }
        }

        // Print summary to console
        System.out.println("=== QVT-O Parser Benchmark Results ===");
        System.out.println("Detailed CSV: " + detailedCsvPath.toAbsolutePath());
        System.out.println("Summary CSV:  " + summaryCsvPath.toAbsolutePath());
        System.out.println("Total files tested: " + results.size());
        System.out.println();
        System.out.printf("%-45s %6s %9s %11s %12s %9s%n",
                "Model / Strategy", "Files", "Parsed", "Parse Rate", "Avg Problems", "Avg chrF");
        System.out.println("-".repeat(95));

        for (var entry : grouped.entrySet()) {
            List<String[]> rows = entry.getValue();
            String[] keyParts = entry.getKey().split(",", 2);
            String label = keyParts[0] + " / " + keyParts[1];
            int totalFiles = rows.size();
            long parsedOk = rows.stream().filter(r -> Boolean.parseBoolean(r[4])).count();
            double parseRate = (double) parsedOk / totalFiles * 100.0;
            double avgProblems = rows.stream()
                    .mapToInt(r -> Math.max(0, Integer.parseInt(r[3])))
                    .average().orElse(0);
            double avgChrF = rows.stream()
                    .mapToDouble(r -> Double.parseDouble(r[5]))
                    .average().orElse(0);

            System.out.printf(Locale.US, "%-45s %6d %7d %10.1f%% %12.2f %9.4f%n",
                    label, totalFiles, parsedOk, parseRate, avgProblems, avgChrF);
        }
    }

    /**
     * Compute chrF score (character n-gram F-score) between hypothesis and reference.
     * Uses n-gram orders 1 to CHRF_MAX_N with beta=CHRF_BETA.
     */
    static double computeChrF(String hypothesis, String reference) {
        hypothesis = hypothesis.strip();
        reference = reference.strip();

        if (hypothesis.isEmpty() && reference.isEmpty()) return 1.0;
        if (hypothesis.isEmpty() || reference.isEmpty()) return 0.0;

        double totalPrecision = 0;
        double totalRecall = 0;
        int validOrders = 0;

        for (int n = 1; n <= CHRF_MAX_N; n++) {
            Map<String, Integer> hypNgrams = extractCharNgrams(hypothesis, n);
            Map<String, Integer> refNgrams = extractCharNgrams(reference, n);

            if (hypNgrams.isEmpty() && refNgrams.isEmpty()) continue;

            int matchCount = 0;
            for (var entry : hypNgrams.entrySet()) {
                matchCount += Math.min(entry.getValue(),
                        refNgrams.getOrDefault(entry.getKey(), 0));
            }

            int hypTotal = hypNgrams.values().stream().mapToInt(Integer::intValue).sum();
            int refTotal = refNgrams.values().stream().mapToInt(Integer::intValue).sum();

            double precision = hypTotal > 0 ? (double) matchCount / hypTotal : 0;
            double recall = refTotal > 0 ? (double) matchCount / refTotal : 0;

            totalPrecision += precision;
            totalRecall += recall;
            validOrders++;
        }

        if (validOrders == 0) return 0.0;

        double avgPrecision = totalPrecision / validOrders;
        double avgRecall = totalRecall / validOrders;

        if (avgPrecision + avgRecall == 0) return 0.0;

        double betaSq = CHRF_BETA * CHRF_BETA;
        return (1 + betaSq) * avgPrecision * avgRecall / (betaSq * avgPrecision + avgRecall);
    }

    static Map<String, Integer> extractCharNgrams(String text, int n) {
        Map<String, Integer> ngrams = new HashMap<>();
        for (int i = 0; i <= text.length() - n; i++) {
            String ngram = text.substring(i, i + n);
            ngrams.merge(ngram, 1, Integer::sum);
        }
        return ngrams;
    }
}
