package com.example.atlparser;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.m2m.atl.engine.parser.AtlParser;

import java.io.FileInputStream;
import java.io.InputStream;

/**
 * ATL Parser Main - same logic as AtlParserTest
 *
 * Output format: RESULT:OK:0 or RESULT:FAIL:problemCount
 */
public class ATLParserMain {

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: ATLParserMain <atl-file>");
            System.exit(1);
        }

        String atlFilePath = args[0];

        try {
            AtlParser parser = AtlParser.getDefault();

            try (InputStream input = new FileInputStream(atlFilePath)) {
                EObject[] result = parser.parseWithProblems(input);

                if (result == null || result[0] == null) {
                    System.out.println("RESULT:FAIL:-1");
                    System.exit(1);
                }

                // Same logic as AtlParserTest
                int problemCount = result.length - 1;

                if (problemCount > 0) {
                    System.out.println("RESULT:FAIL:" + problemCount);
                    System.err.println("FAIL: " + atlFilePath + " (" + problemCount + " errors)");
                    for (int i = 1; i < result.length; i++) {
                        System.err.println("  - " + result[i]);
                    }
                    System.exit(1);
                } else {
                    System.out.println("RESULT:OK:0");
                    System.exit(0);
                }
            }
        } catch (Exception e) {
            System.out.println("RESULT:FAIL:-1");
            System.err.println("ERROR: " + e.getMessage());
            System.exit(1);
        }
    }
}
