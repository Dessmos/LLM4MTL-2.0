package org.qvto.parser;

import org.antlr.v4.runtime.*;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class QVTOParserFacade {

    private final List<String> problems = new ArrayList<>();

    public QVTOParser.CompilationUnitContext parse(String source) {
        CharStream input = CharStreams.fromString(source);
        return doParse(input);
    }

    public QVTOParser.CompilationUnitContext parseFile(Path path) throws IOException {
        CharStream input = CharStreams.fromPath(path);
        return doParse(input);
    }

    private QVTOParser.CompilationUnitContext doParse(CharStream input) {
        problems.clear();

        QVTOLexer lexer = new QVTOLexer(input);
        lexer.removeErrorListeners();
        lexer.addErrorListener(new CollectingErrorListener());

        CommonTokenStream tokens = new CommonTokenStream(lexer);

        QVTOParser parser = new QVTOParser(tokens);
        parser.removeErrorListeners();
        parser.addErrorListener(new CollectingErrorListener());

        return parser.compilationUnit();
    }

    public List<String> getProblems() {
        return Collections.unmodifiableList(problems);
    }

    public int getProblemCount() {
        return problems.size();
    }

    private class CollectingErrorListener extends BaseErrorListener {
        @Override
        public void syntaxError(Recognizer<?, ?> recognizer, Object offendingSymbol,
                                int line, int charPositionInLine,
                                String msg, RecognitionException e) {
            String problem = "line " + line + ":" + charPositionInLine + " " + msg;
            problems.add(problem);
        }
    }
}
