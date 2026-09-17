package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class MultipleTargetsTest extends FlowchartTestBase {

    @Test
    public void testMultipleTargets() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/multiple_targets.etl", sourceModel, targetModel);

        // Action2Elements: transforms actions with guard (outgoing.notEmpty())
        // Actions: "Wake up"(has outgoing), "Sleep"(has outgoing), "Get up"(NO outgoing), "begin"(has outgoing)
        // So 3 actions pass the guard + 1 decision = 4 DIV containers
        Collection<?> divs = targetModel.getAllOfType("DIV");
        assertEquals(4, divs.size(),
            "Should have 4 DIV containers (3 actions with outgoing + 1 decision)");

        // H1 titles: 3 from Action2Elements + 1 from Decision2Elements = 4
        Collection<?> h1Elements = targetModel.getAllOfType("H1");
        assertEquals(4, h1Elements.size(), "Should have 4 H1 title elements");

        // A elements: 3 from Action2Elements (one per action) + 2 from Decision2Elements (decision has 2 outgoing)
        Collection<?> aElements = targetModel.getAllOfType("A");
        assertTrue(aElements.size() >= 3,
            "Should have A link elements from actions and decisions");
    }
}
