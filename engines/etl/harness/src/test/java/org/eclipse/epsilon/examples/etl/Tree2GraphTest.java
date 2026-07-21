package org.eclipse.epsilon.examples.etl;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.util.Collection;

import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.eol.models.IModel;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

public class Tree2GraphTest extends EtlTestBase {

    @BeforeEach
    public void setUp() throws Exception {
        registerMetamodel("metamodels/Tree.ecore");
        registerMetamodel("metamodels/Graph.ecore");
    }

    @Test
    public void testTree2Graph() throws Exception {
        EmfModel sourceModel = createEmfModel("Tree", "models/tree.model",
            "Tree", true, false);

        File tempFile = File.createTempFile("graph_output", ".model");
        tempFile.deleteOnExit();
        EmfModel targetModel = createEmfModelFromFile("Graph", tempFile.getAbsolutePath(),
            "Graph", false, false);

        runEtl("transformations/Tree2Graph.etl", sourceModel, targetModel);

        // Get all Node instances from the target model
        Collection<?> nodes = targetModel.getAllOfType("Node");
        assertEquals(2, nodes.size(), "Should have 2 nodes");

        // Get all Edge instances
        Collection<?> edges = targetModel.getAllOfType("Edge");
        assertEquals(1, edges.size(), "Should have 1 edge (from parent to child)");

        // Verify node names
        boolean hasT1 = false, hasT2 = false;
        for (Object node : nodes) {
            org.eclipse.emf.ecore.EObject eObj = (org.eclipse.emf.ecore.EObject) node;
            Object name = eObj.eGet(eObj.eClass().getEStructuralFeature("name"));
            if ("t1".equals(name)) hasT1 = true;
            if ("t2".equals(name)) hasT2 = true;
        }
        assertTrue(hasT1, "Should have node named 't1'");
        assertTrue(hasT2, "Should have node named 't2'");
    }
}
