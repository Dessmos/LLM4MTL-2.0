package tools.vitruv.reactionsparser.parser;



public class PureAntlrParserTest {

  //   @Test
  //   void testParseValidFile() throws IOException {
  //     PureAntlrParser parser = new PureAntlrParser();
  //     PureAntlrParser.ParseResult result =
  // parser.parse(resourcePath("resources/template.reactions"));

  //     System.out.println("Parse tree: " + result.getParseTree().toStringTree());
  //     System.out.println("Error count: " + result.getErrorCount());

  //     for (PureAntlrParser.SyntaxError error : result.getErrors()) {
  //       System.err.println(error);
  //     }

  //     // The template.reactions file should parse without errors
  //     assertEquals(0, result.getErrorCount(), "Expected no syntax errors");
  //   }

  //   @Test
  //   void testParseMultipleFiles() throws IOException {
  //     PureAntlrParser parser = new PureAntlrParser();

  //     // Parse template.reactions
  //     PureAntlrParser.ParseResult result1 = parser.parse(resourcePath("template.reactions"));
  //     System.out.println("template.reactions errors: " + result1.getErrorCount());

  //     // Parse template2.reactions
  //     PureAntlrParser.ParseResult result2 = parser.parse(resourcePath("template2.reactions"));
  //     System.out.println("template2.reactions errors: " + result2.getErrorCount());

  //     // Print any errors
  //     for (PureAntlrParser.SyntaxError error : result1.getErrors()) {
  //       System.err.println("template.reactions: " + error);
  //     }
  //     for (PureAntlrParser.SyntaxError error : result2.getErrors()) {
  //       System.err.println("template2.reactions: " + error);
  //     }
  //   }

  //   @Test
  //   void testParseStringWithErrors() {
  //     PureAntlrParser parser = new PureAntlrParser();

  //     // Invalid content - should have syntax errors
  //     String invalidContent = "import invalid syntax here";
  //     PureAntlrParser.ParseResult result = parser.parseString(invalidContent);

  //     System.out.println("Invalid content error count: " + result.getErrorCount());
  //     for (PureAntlrParser.SyntaxError error : result.getErrors()) {
  //       System.err.println(error);
  //     }

  //     assertTrue(result.hasErrors(), "Expected syntax errors for invalid content");
  //   }

  //   @Test
  //   void testCountErrors() throws IOException {
  //     PureAntlrParser parser = new PureAntlrParser();
  //     int errorCount = parser.countErrors(resourcePath("template.reactions"));
  //     System.out.println("Total errors in template.reactions: " + errorCount);
  //   }

  //   @Test
  //   void testFileWithKnownErrors() throws IOException {
  //     PureAntlrParser parser = new PureAntlrParser();
  //     PureAntlrParser.ParseResult result = parser.parse(resourcePath("with_errors.reactions"));

  //     System.out.println("=== with_errors.reactions ===");
  //     System.out.println("Error count: " + result.getErrorCount());
  //     for (PureAntlrParser.SyntaxError error : result.getErrors()) {
  //       System.out.println("  " + error);
  //     }

  //     // File has 2 known errors: "aftr" and "updat"
  //     assertTrue(result.hasErrors(), "Should have syntax errors");
  //   }

  //   private String resourcePath(String fileName) {
  //     return new File(this.getClass().getClassLoader().getResource(fileName).getFile())
  //         .getAbsolutePath();
  //   }
}
