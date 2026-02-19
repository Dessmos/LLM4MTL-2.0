package tools.vitruv.reactionsparser;

import java.io.IOException;

import tools.vitruv.reactionsparser.parser.PureAntlrParser;

/** Main class for running the Reactions parser from command line. */
public class Main {

  public static void main(String[] args) {
    if (args.length == 0) {
      System.err.println("Usage: java -jar reactionsparser.jar <filepath> [<filepath2> ...]");
      System.err.println("  Parse one or more .reactions files and report syntax errors");
      System.exit(1);
    }

    PureAntlrParser parser = new PureAntlrParser();
    int totalErrors = 0;
    int filesWithErrors = 0;
    int totalFiles = args.length;

    for (String filePath : args) {
      System.out.println("\n========================================");
      System.out.println("Parsing: " + filePath);
      System.out.println("========================================");

      try {
        PureAntlrParser.ParseResult result = parser.parse(filePath);

        if (result.hasErrors()) {
          System.err.println("Found " + result.getErrorCount() + " syntax error(s):");
          for (PureAntlrParser.SyntaxError error : result.getErrors()) {
            System.err.println("  " + error);
          }
          totalErrors += result.getErrorCount();
          System.out.println("RESULT\t" + filePath + "\t" + result.getErrorCount());
          filesWithErrors++;
        } else {
          System.out.println("✓ No syntax errors found");
        }

      } catch (IOException e) {
        System.err.println("Error reading file: " + e.getMessage());
        filesWithErrors++;
      }
    }

    // Summary
    System.out.println("\n========================================");
    System.out.println("Summary:");
    System.out.println("  Total files: " + totalFiles);
    System.out.println("  Files with errors: " + filesWithErrors);
    System.out.println("  Total syntax errors: " + totalErrors);
    System.out.println("========================================");

    // Exit with error code if any files had errors
    if (filesWithErrors > 0) {
      System.exit(1);
    } else {
      System.exit(0);
    }
  }
}
