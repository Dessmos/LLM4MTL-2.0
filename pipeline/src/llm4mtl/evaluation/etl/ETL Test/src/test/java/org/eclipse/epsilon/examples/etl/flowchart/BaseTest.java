package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class BaseTest extends FlowchartTestBase {

    @Test
    public void testBase() throws Exception {
        EmfModel sourceModel = loadWakeupModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/base.etl", sourceModel, targetModel);

        // base.etl creates H1 for: Flowchart, Actions, Decisions, Transitions
        Collection<?> h1Elements = targetModel.getAllOfType("H1");

        Set<String> values = h1Elements.stream()
            .map(e -> {
                EObject eObj = (EObject) e;
                return (String) eObj.eGet(eObj.eClass().getEStructuralFeature("value"));
            })
            .collect(Collectors.toSet());

        // Flowchart name
        assertTrue(values.contains("Wakeup"), "Should have H1 for Flowchart name");

        // Action names: Wake up, Sleep, Get up, begin
        assertTrue(values.contains("Wake up"), "Should have H1 for 'Wake up' action");
        assertTrue(values.contains("Sleep"), "Should have H1 for 'Sleep' action");
        assertTrue(values.contains("Get up"), "Should have H1 for 'Get up' action");
        assertTrue(values.contains("begin"), "Should have H1 for 'begin' action");

        // Decision name
        assertTrue(values.contains("Is it really too early?"),
            "Should have H1 for decision");

        // Transition names: "", "Yes", "Some Time Passes", "No", "start"
        assertTrue(values.contains("Yes"), "Should have H1 for 'Yes' transition");
        assertTrue(values.contains("No"), "Should have H1 for 'No' transition");

        // Total: 1 flowchart + 4 actions + 1 decision + 5 transitions = 11
        assertEquals(11, h1Elements.size(),
            "Should have 11 H1 elements (1 flowchart + 4 actions + 1 decision + 5 transitions)");
    }
}
