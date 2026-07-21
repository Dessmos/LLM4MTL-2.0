package tools.vitruv.reactionsparser.parser;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import org.antlr.v4.runtime.BaseErrorListener;
import org.antlr.v4.runtime.CharStream;
import org.antlr.v4.runtime.CharStreams;
import org.antlr.v4.runtime.CommonTokenStream;
import org.antlr.v4.runtime.RecognitionException;
import org.antlr.v4.runtime.Recognizer;
import org.antlr.v4.runtime.tree.ParseTree;
import tools.vitruv.reactionsparser.parser.antlr.DebugInternalReactionsLanguageLexer;
import tools.vitruv.reactionsparser.parser.antlr.DebugInternalReactionsLanguageParser;

/**
 * Pure ANTLR4 parser for Reactions language files. No Xtext dependencies - just counts syntax
 * errors.
 */
public class PureAntlrParser {

  /** Represents a syntax error found during parsing. */
  public static class SyntaxError {
    private final int line;
    private final int charPositionInLine;
    private final String message;
    private final Object offendingSymbol;

    public SyntaxError(int line, int charPositionInLine, String message, Object offendingSymbol) {
      this.line = line;
      this.charPositionInLine = charPositionInLine;
      this.message = message;
      this.offendingSymbol = offendingSymbol;
    }

    public int getLine() {
      return line;
    }

    public int getCharPositionInLine() {
      return charPositionInLine;
    }

    public String getMessage() {
      return message;
    }

    public Object getOffendingSymbol() {
      return offendingSymbol;
    }

    @Override
    public String toString() {
      return String.format("Line %d:%d - %s", line, charPositionInLine, message);
    }
  }

  /** Result of parsing a file. */
  public static class ParseResult {
    private final ParseTree parseTree;
    private final List<SyntaxError> errors;

    public ParseResult(ParseTree parseTree, List<SyntaxError> errors) {
      this.parseTree = parseTree;
      this.errors = errors;
    }

    public ParseTree getParseTree() {
      return parseTree;
    }

    public List<SyntaxError> getErrors() {
      return errors;
    }

    public int getErrorCount() {
      return errors.size();
    }

    public boolean hasErrors() {
      return !errors.isEmpty();
    }
  }

  /** Error listener that collects all syntax errors. */
  private static class CollectingErrorListener extends BaseErrorListener {
    private final List<SyntaxError> errors = new ArrayList<>();

    @Override
    public void syntaxError(
        Recognizer<?, ?> recognizer,
        Object offendingSymbol,
        int line,
        int charPositionInLine,
        String msg,
        RecognitionException e) {
      errors.add(new SyntaxError(line, charPositionInLine, msg, offendingSymbol));
    }

    public List<SyntaxError> getErrors() {
      return errors;
    }
  }

  /**
   * Parse a reactions file and return the result with error count.
   *
   * @param filePath Path to the .reactions file
   * @return ParseResult containing parse tree and list of syntax errors
   * @throws IOException if file cannot be read
   */
  public ParseResult parse(String filePath) throws IOException {
    CharStream charStream = CharStreams.fromFileName(filePath);
    DebugInternalReactionsLanguageLexer lexer = new DebugInternalReactionsLanguageLexer(charStream);
    CommonTokenStream tokens = new CommonTokenStream(lexer);
    DebugInternalReactionsLanguageParser parser = new DebugInternalReactionsLanguageParser(tokens);

    // Remove default error listeners and add our collecting listener
    CollectingErrorListener errorListener = new CollectingErrorListener();
    lexer.removeErrorListeners();
    lexer.addErrorListener(errorListener);
    parser.removeErrorListeners();
    parser.addErrorListener(errorListener);

    // Parse starting from the root rule
    ParseTree parseTree = parser.ruleReactionsFile();

    return new ParseResult(parseTree, errorListener.getErrors());
  }

  /**
   * Parse a reactions file and return just the error count.
   *
   * @param filePath Path to the .reactions file
   * @return Number of syntax errors found
   * @throws IOException if file cannot be read
   */
  public int countErrors(String filePath) throws IOException {
    return parse(filePath).getErrorCount();
  }

  /**
   * Parse a reactions file from a string content.
   *
   * @param content The reactions file content as a string
   * @return ParseResult containing parse tree and list of syntax errors
   */
  public ParseResult parseString(String content) {
    CharStream charStream = CharStreams.fromString(content);
    DebugInternalReactionsLanguageLexer lexer = new DebugInternalReactionsLanguageLexer(charStream);
    CommonTokenStream tokens = new CommonTokenStream(lexer);
    DebugInternalReactionsLanguageParser parser = new DebugInternalReactionsLanguageParser(tokens);

    CollectingErrorListener errorListener = new CollectingErrorListener();
    lexer.removeErrorListeners();
    lexer.addErrorListener(errorListener);
    parser.removeErrorListeners();
    parser.addErrorListener(errorListener);

    ParseTree parseTree = parser.ruleReactionsFile();

    return new ParseResult(parseTree, errorListener.getErrors());
  }
}
