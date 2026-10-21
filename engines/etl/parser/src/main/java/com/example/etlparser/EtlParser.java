package com.example.etlparser;

import org.eclipse.epsilon.common.parse.problem.ParseProblem;
import org.eclipse.epsilon.etl.EtlModule;

import java.io.File;
import java.util.List;

public class EtlParser {

    private final EtlModule module;

    public EtlParser() {
        this.module = new EtlModule();
    }

    public boolean parse(String etlPath) throws Exception {
        return module.parse(new File(etlPath).toURI());
    }

    public List<ParseProblem> getParseProblems() {
        return module.getParseProblems();
    }

    public long getErrorCount() {
        return module.getParseProblems().stream()
                .filter(p -> p.getSeverity() == ParseProblem.ERROR)
                .count();
    }

    public long getWarningCount() {
        return module.getParseProblems().stream()
                .filter(p -> p.getSeverity() == ParseProblem.WARNING)
                .count();
    }
}
