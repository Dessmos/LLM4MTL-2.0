package com.example.etlparser;

import org.eclipse.epsilon.common.parse.problem.ParseProblem;
import org.junit.Test;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.Assert.*;

public class EtlParserTest {

    @Test
    public void testAllEtlFiles() throws Exception {
        Path transformationsDir = resolveResourceDir("/transformations");
        List<Path> etlFiles;
        try (Stream<Path> stream = Files.list(transformationsDir)) {
            etlFiles = stream.filter(p -> p.toString().endsWith(".etl")).sorted().toList();
        }

        assertFalse("Should find at least one .etl file", etlFiles.isEmpty());
        System.out.println("Found " + etlFiles.size() + " ETL files\n");

        int totalErrors = 0;
        int totalWarnings = 0;

        for (Path etlFile : etlFiles) {
            EtlParser parser = new EtlParser();
            boolean parsed = parser.parse(etlFile.toAbsolutePath().toString());
            List<ParseProblem> problems = parser.getParseProblems();
            long errors = parser.getErrorCount();
            long warnings = parser.getWarningCount();
            totalErrors += errors;
            totalWarnings += warnings;

            System.out.println("--- " + etlFile.getFileName() + " ---");
            System.out.println("  Parsed: " + parsed + " | Problems: " + problems.size()
                    + " (Errors: " + errors + ", Warnings: " + warnings + ")");
            for (ParseProblem p : problems) {
                System.out.println("  [" + (p.getSeverity() == ParseProblem.ERROR ? "ERROR" : "WARNING")
                        + "] line " + p.getLine() + ":" + p.getColumn() + " - " + p.getReason());
            }
        }

        System.out.println("\n=== Summary ===");
        System.out.println("Files: " + etlFiles.size()
                + " | Total Errors: " + totalErrors
                + " | Total Warnings: " + totalWarnings);

        assertEquals("Should have no parse errors across all ETL files", 0, totalErrors);
    }

    private Path resolveResourceDir(String resourcePath) {
        var url = getClass().getResource(resourcePath);
        if (url == null) {
            throw new RuntimeException("Resource not found: " + resourcePath);
        }
        try {
            return Paths.get(url.toURI());
        } catch (URISyntaxException e) {
            throw new RuntimeException("Invalid resource URI: " + url, e);
        }
    }
}
