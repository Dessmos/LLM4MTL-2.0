package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class GreedyTest extends FlowchartTestBase {

    @Test
    public void testGreedy() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/greedy.etl", sourceModel, targetModel);

        // @greedy rule matches NamedElement, which includes:
        // Flowchart (1) + Actions (4) + Decision (1) + Transitions (5) = 11
        Collection<?> h1Elements = targetModel.getAllOfType("H1");
        assertEquals(11, h1Elements.size(),
            "Should have 11 H1 elements (1 flowchart + 4 actions + 1 decision + 5 transitions)");
    }
}
