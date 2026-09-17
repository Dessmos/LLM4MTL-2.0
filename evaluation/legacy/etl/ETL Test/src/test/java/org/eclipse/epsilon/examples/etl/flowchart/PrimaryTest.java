package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class PrimaryTest extends FlowchartTestBase {

    @Test
    public void testPrimary() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/primary.etl", sourceModel, targetModel);

        // Flowchart2Heading creates 1 DIV and adds only t.equivalents().first (the @primary H1)
        Collection<?> divs = targetModel.getAllOfType("DIV");
        assertEquals(1, divs.size(), "Should have 1 DIV from Flowchart");

        // @primary Transition2Heading creates H1 for each transition
        // 5 transitions in wakeup.model
        Collection<?> h1Elements = targetModel.getAllOfType("H1");
        assertEquals(5, h1Elements.size(),
            "Should have 5 H1 elements (one per transition, from @primary rule)");

        // Transition2SourceLink and Transition2TargetLink create A elements
        // 5 transitions x 2 = 10 A elements
        Collection<?> aElements = targetModel.getAllOfType("A");
        assertEquals(10, aElements.size(),
            "Should have 10 A elements (source + target link per transition)");
    }
}
