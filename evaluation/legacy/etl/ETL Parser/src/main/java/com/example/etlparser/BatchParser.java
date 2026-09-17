package com.example.etlparser;

import org.eclipse.epsilon.common.parse.problem.ParseProblem;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;

public class BatchParser {

    private static final String[] MODELS = {"claude-sonnet-4", "gemini-2-5-pro", "gpt-5"};
    private static final String[] STRATEGIES = {"only_prompt", "grammar", "few_shot", "few_shots_AND_grammar"};

    public static void main(String[] args) throws Exception {
        Path resourcesDir;
        if (args.length > 0) {
            resourcesDir = Paths.get(args[0]);
        } else {
            resourcesDir = Paths.get("src/main/resources");
        }

        // CSV header
        System.out.println("model,strategy,filename,parsed,total_problems,errors,warnings,error_details");

        for (String model : MODELS) {
            for (String strategy : STRATEGIES) {
                parseDirectory(resourcesDir, model, strategy);
            }
        }
    }

    private static void parseDirectory(Path resourcesDir, String model, String strategy) throws Exception {
        Path dir = resourcesDir.resolve(model).resolve(strategy);
        if (!Files.isDirectory(dir)) {
            System.err.println("Directory not found: " + dir);
            return;
        }

        List<Path> etlFiles;
        try (Stream<Path> stream = Files.list(dir)) {
            etlFiles = stream.filter(p -> p.toString().endsWith(".etl")).sorted().toList();
        }
        for (Path etlFile : etlFiles) {
            parseFile(model, strategy, etlFile);
        }
    }

    private static void parseFile(String model, String strategy, Path etlFile) {
        EtlParser parser = new EtlParser();
        boolean parsed = false;
        try {
            parsed = parser.parse(etlFile.toAbsolutePath().toString());
        } catch (Exception e) {
            // parse failed entirely
        }

        List<ParseProblem> problems = parser.getParseProblems();
        String details = problemDetails(problems);
        String detailStr = "\"" + details.replace("\"", "\"\"") + "\"";
        System.out.println(String.join(",",
                model,
                strategy,
                etlFile.getFileName().toString(),
                String.valueOf(parsed),
                String.valueOf(problems.size()),
                String.valueOf(parser.getErrorCount()),
                String.valueOf(parser.getWarningCount()),
                detailStr));
    }

    private static String problemDetails(List<ParseProblem> problems) {
        StringBuilder details = new StringBuilder();
        for (ParseProblem problem : problems) {
            if (details.length() > 0) details.append(" | ");
            String severity = problem.getSeverity() == ParseProblem.ERROR ? "ERROR" : "WARNING";
            details.append("[").append(severity).append("] line ")
                    .append(problem.getLine()).append(":").append(problem.getColumn())
                    .append(" - ").append(problem.getReason());
        }
        return details.toString();
    }
}
