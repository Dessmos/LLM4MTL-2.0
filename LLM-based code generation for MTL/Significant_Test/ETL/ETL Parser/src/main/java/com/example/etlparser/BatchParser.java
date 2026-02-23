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
                Path dir = resourcesDir.resolve(model).resolve(strategy);
                if (!Files.isDirectory(dir)) {
                    System.err.println("Directory not found: " + dir);
                    continue;
                }

                List<Path> etlFiles;
                try (Stream<Path> stream = Files.list(dir)) {
                    etlFiles = stream.filter(p -> p.toString().endsWith(".etl")).sorted().toList();
                }

                for (Path etlFile : etlFiles) {
                    EtlParser parser = new EtlParser();
                    boolean parsed = false;
                    try {
                        parsed = parser.parse(etlFile.toAbsolutePath().toString());
                    } catch (Exception e) {
                        // parse failed entirely
                    }

                    List<ParseProblem> problems = parser.getParseProblems();
                    long errors = parser.getErrorCount();
                    long warnings = parser.getWarningCount();

                    StringBuilder details = new StringBuilder();
                    for (ParseProblem p : problems) {
                        if (details.length() > 0) details.append(" | ");
                        String severity = p.getSeverity() == ParseProblem.ERROR ? "ERROR" : "WARNING";
                        details.append("[").append(severity).append("] line ")
                               .append(p.getLine()).append(":").append(p.getColumn())
                               .append(" - ").append(p.getReason());
                    }

                    String filename = etlFile.getFileName().toString();
                    String detailStr = "\"" + details.toString().replace("\"", "\"\"") + "\"";

                    System.out.println(String.join(",",
                            model,
                            strategy,
                            filename,
                            String.valueOf(parsed),
                            String.valueOf(problems.size()),
                            String.valueOf(errors),
                            String.valueOf(warnings),
                            detailStr));
                }
            }
        }
    }
}
