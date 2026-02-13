package org.qvto.parser;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

class QVTOParserTest {

    private static final Path RESOURCE_DIR =
            Paths.get("src/test/resources/transformation");

    static Stream<String> qvtoFiles() throws IOException {
        return Files.list(RESOURCE_DIR)
                .filter(p -> p.toString().endsWith(".qvto"))
                .map(p -> p.getFileName().toString())
                .sorted();
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("qvtoFiles")
    void parseShouldSucceedWithZeroProblems(String fileName) throws IOException {
        Path filePath = RESOURCE_DIR.resolve(fileName);
        String source = Files.readString(filePath);

        QVTOParserFacade facade = new QVTOParserFacade();
        QVTOParser.CompilationUnitContext tree = facade.parse(source);

        assertNotNull(tree, "Parse tree should not be null for " + fileName);

        if (facade.getProblemCount() > 0) {
            System.err.println("=== Problems in " + fileName
                    + " (count=" + facade.getProblemCount() + ") ===");
            facade.getProblems().forEach(p -> System.err.println("  " + p));
        } else {
            System.out.println("[PASS] " + fileName + " - problem count: 0");
        }

        assertEquals(0, facade.getProblemCount(),
                "Expected 0 problems for " + fileName
                        + " but got: " + facade.getProblems());
    }
}
