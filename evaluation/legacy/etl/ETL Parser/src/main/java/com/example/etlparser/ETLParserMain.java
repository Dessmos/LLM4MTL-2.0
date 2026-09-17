package com.example.etlparser;

import org.eclipse.epsilon.common.parse.problem.ParseProblem;

import java.util.List;

/**
 * Single-file ETL parser entry point.
 *
 * Usage: java ... ETLParserMain <etl-file-path>
 * Output: RESULT:OK:0  or  RESULT:FAIL:<problem_count>
 */
public class ETLParserMain {

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: ETLParserMain <etl-file-path>");
            System.exit(1);
        }

        String etlPath = args[0];
        try {
            EtlParser parser = new EtlParser();
            parser.parse(etlPath);
            List<ParseProblem> problems = parser.getParseProblems();
            int problemCount = problems.size();

            if (problemCount == 0) {
                System.out.println("RESULT:OK:0");
            } else {
                System.out.println("RESULT:FAIL:" + problemCount);
            }
        } catch (Exception e) {
            System.out.println("RESULT:FAIL:-1");
        }
    }
}
