package org.eclipse.epsilon.examples.etl.flowchart;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.Test;

public class InheritanceTest extends FlowchartTestBase {

    @Test
    public void testInheritance() throws Exception {
        EmfModel sourceModel = loadWakeupWithSubflowModel();
        EmfModel targetModel = createHtmlModel();

        runEtl("transformations/inheritance.etl", sourceModel, targetModel);

        Collection<?> h1Elements = targetModel.getAllOfType("H1");

        Set<String> values = h1Elements.stream()
            .map(e -> {
                EObject eObj = (EObject) e;
                return (String) eObj.eGet(eObj.eClass().getEStructuralFeature("value"));
            })
            .collect(Collectors.toSet());

        // Flowchart2H1 produces "Flowchart Wakeup"
        assertTrue(values.contains("Flowchart Wakeup"),
            "Should have 'Flowchart Wakeup' from Flowchart2H1 rule");

        // Subflow2H1 extends Flowchart2H1, producing "Subflow Flowchart Snoozing"
        assertTrue(values.contains("Subflow Flowchart Snoozing"),
            "Should have 'Subflow Flowchart Snoozing' from Subflow2H1 rule");

        // 1 Flowchart + 1 Subflow = 2 H1 elements
        assertEquals(2, h1Elements.size(),
            "Should have 2 H1 elements (1 Flowchart + 1 Subflow)");
    }
}
