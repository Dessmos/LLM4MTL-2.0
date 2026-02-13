package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class LazyTest extends FlowchartTestBase {

    @Test
    public void testLazy() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/lazy.etl", sourceModel, targetModel);

        // Flowchart2Heading creates a DIV and calls f.nodes.equivalent()
        Collection<?> divs = targetModel.getAllOfType("DIV");
        assertEquals(1, divs.size(), "Should have 1 DIV from Flowchart");

        // @lazy Action2Heading and Decision2Heading are invoked via .equivalent()
        // 4 Actions + 1 Decision = 5 nodes, all invoked via equivalent()
        Collection<?> h1Elements = targetModel.getAllOfType("H1");
        assertEquals(5, h1Elements.size(),
            "Should have 5 H1 elements (4 actions + 1 decision, but NOT transitions)");
    }
}
