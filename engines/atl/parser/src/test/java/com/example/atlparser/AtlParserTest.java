package com.example.atlparser;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.m2m.atl.engine.parser.AtlParser;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class AtlParserTest {

    private static final String[] ATL_FILES = {
        "AmaltheaToAscet_All.atl",
        "FamiliesToPersons_All.atl",
        "BibTeX2DocBook_All.atl",
        "CPL2SPL_All.atl",
        "DSL2KM3_All.atl",
        "Grafcet2PetriNet_All.atl",
        "IEEE1471_2_MoDAF_All.atl",
        "Make2Ant_All.atl",
        "PetriNet2Grafcet_All.atl",
        "XML2DSL_All.atl",
        "NetworkToGraph_All.atl",
        "User2Account_All.atl",
        "Class2Interface_All.atl",
        "Item2Product_All.atl",
        "Document2Report_All.atl"
    };

    @Test
    void testParseAllAtlFiles() throws Exception {
        AtlParser parser = AtlParser.getDefault();
        List<String> failures = new ArrayList<>();

        for (String fileName : ATL_FILES) {
            try (InputStream input = getClass().getClassLoader().getResourceAsStream(fileName)) {
                assertNotNull(input, "File not found: " + fileName);

                EObject[] result = parser.parseWithProblems(input);
                assertNotNull(result[0], "Failed to parse: " + fileName);

                int problemCount = result.length - 1;

                if (problemCount > 0) {
                    System.out.println("FAIL: " + fileName + " (" + problemCount + " errors)");
                    for (int i = 1; i < result.length; i++) {
                        System.out.println("  - " + result[i]);
                    }
                    failures.add(fileName + " (" + problemCount + " errors)");
                } else {
                    System.out.println("OK: " + fileName);
                }
            }
        }

        if (!failures.isEmpty()) {
            fail("Files with syntax errors:\n  " + String.join("\n  ", failures));
        }
    }
}
