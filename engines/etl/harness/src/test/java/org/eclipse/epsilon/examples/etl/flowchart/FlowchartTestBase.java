package org.eclipse.epsilon.examples.etl.flowchart;

import java.io.File;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.examples.etl.EtlTestBase;
import org.junit.jupiter.api.BeforeEach;

public abstract class FlowchartTestBase extends EtlTestBase {

    @BeforeEach
    public void registerFlowchartMetamodels() throws Exception {
        registerMetamodel("metamodels/Flowchart.ecore");
        registerMetamodel("metamodels/HTML.ecore");
    }

    protected EmfModel loadWakeupModel() throws Exception {
        return createEmfModel("Flowchart", "models/wakeup.model",
            "flowchart", true, false);
    }

    protected EmfModel loadWakeupWithSubflowModel() throws Exception {
        return createEmfModel("Flowchart", "models/wakeup_with_subflow.model",
            "flowchart", true, false);
    }

    protected EmfModel createHtmlModel() throws Exception {
        File tempFile = File.createTempFile("html_output", ".model");
        tempFile.deleteOnExit();
        return createEmfModelFromFile("HTML", tempFile.getAbsolutePath(),
            "HTML", false, false);
    }
}
