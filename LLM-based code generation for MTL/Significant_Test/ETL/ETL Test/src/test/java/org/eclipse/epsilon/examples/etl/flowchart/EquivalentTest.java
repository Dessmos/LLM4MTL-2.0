package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class EquivalentTest extends FlowchartTestBase {

    @Test
    public void testEquivalent() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/equivalent.etl", sourceModel, targetModel);

        // equivalent.etl creates: 1 DIV (from Flowchart) containing transition H1s
        Collection<?> divs = targetModel.getAllOfType("DIV");
        assertEquals(1, divs.size(), "Should have 1 DIV from Flowchart");

        // H1 for each Transition (5 transitions in wakeup.model)
        Collection<?> h1Elements = targetModel.getAllOfType("H1");
        assertEquals(5, h1Elements.size(),
            "Should have 5 H1 elements (one per transition)");
    }
}
