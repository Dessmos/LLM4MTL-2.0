package com.example.etlparser;

import org.eclipse.epsilon.common.parse.problem.ParseProblem;

import java.util.List;

/**
 * Single-file ETL parser entry point.
 *
 * Usage: java ... ETLParserMain <etl-file-path>
 * Output: RESULT:OK:0  or  RESULT:FAIL:<problem_count>
 * followed, when it failed, by one tab-separated
 * PROBLEM\t<severity>\tline <line>:<column>\t<reason> line per parse problem.
 * The count alone told a refinement loop only that the file was rejected.
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
                for (ParseProblem problem : problems) {
                    System.out.println("PROBLEM\t"
                            + (problem.getSeverity() == ParseProblem.ERROR ? "ERROR" : "WARNING")
                            + "\tline " + problem.getLine() + ":" + problem.getColumn()
                            + "\t" + problem.getReason());
                }
            }
        } catch (Exception e) {
            System.out.println("RESULT:FAIL:-1");
            System.out.println("PROBLEM\tERROR\t-\t" + e);
        }
    }
}
