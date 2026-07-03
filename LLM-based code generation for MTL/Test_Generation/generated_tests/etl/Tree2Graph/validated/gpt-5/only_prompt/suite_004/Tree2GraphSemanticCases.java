package org.eclipse.epsilon.examples.etl.generated;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.examples.etl.EtlTestBase;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

public class Tree2GraphSemanticCases extends EtlTestBase {
    private static final String ETL = "transformations/Tree2Graph.etl";

    @BeforeEach
    public void setUp() throws Exception {
        registerMetamodel("metamodels/Tree.ecore");
        registerMetamodel("metamodels/Graph.ecore");
    }

    @Test
    public void singleRootOnly() throws Exception {
        RunResult run = runTransformation("generated-models/tree2graph/single_root_only.model");
        List<String> expectedNodes = Arrays.asList("root");
        List<String> expectedEdges = new ArrayList<>();
        assertEquals(counts(expectedNodes), counts(namesOf(run.target, "Node", "name")), "Node name multiplicities must match expected Tree labels");
        assertEquals(counts(expectedEdges), counts(edgePairs(run.target)), "Edge multiplicities must match expected source->target Node names");
        assertEquals(expectedNodes.size(), allOfType(run.target, "Node").size(), "No superfluous or missing Nodes");
        assertEquals(expectedEdges.size(), allOfType(run.target, "Edge").size(), "No superfluous or missing Edges");
    }

    @Test
    public void threeLevelChain() throws Exception {
        RunResult run = runTransformation("generated-models/tree2graph/three_level_chain.model");
        List<String> expectedNodes = Arrays.asList("A", "B", "C");
        List<String> expectedEdges = Arrays.asList("A->B", "B->C");
        assertEquals(counts(expectedNodes), counts(namesOf(run.target, "Node", "name")), "Node name multiplicities must match expected Tree labels");
        assertEquals(counts(expectedEdges), counts(edgePairs(run.target)), "Edge multiplicities must match expected source->target Node names");
        assertEquals(expectedNodes.size(), allOfType(run.target, "Node").size(), "No superfluous or missing Nodes");
        assertEquals(expectedEdges.size(), allOfType(run.target, "Edge").size(), "No superfluous or missing Edges");
    }

    @Test
    public void branchingTree() throws Exception {
        RunResult run = runTransformation("generated-models/tree2graph/branching_tree.model");
        List<String> expectedNodes = Arrays.asList("root", "left", "right", "left.left");
        List<String> expectedEdges = Arrays.asList("root->left", "root->right", "left->left.left");
        assertEquals(counts(expectedNodes), counts(namesOf(run.target, "Node", "name")), "Node name multiplicities must match expected Tree labels");
        assertEquals(counts(expectedEdges), counts(edgePairs(run.target)), "Edge multiplicities must match expected source->target Node names");
        assertEquals(expectedNodes.size(), allOfType(run.target, "Node").size(), "No superfluous or missing Nodes");
        assertEquals(expectedEdges.size(), allOfType(run.target, "Edge").size(), "No superfluous or missing Edges");
    }

    @Test
    public void repeatedLabels() throws Exception {
        RunResult run = runTransformation("generated-models/tree2graph/repeated_labels.model");
        List<String> expectedNodes = Arrays.asList("dup", "dup", "dup");
        List<String> expectedEdges = Arrays.asList("dup->dup", "dup->dup");
        assertEquals(counts(expectedNodes), counts(namesOf(run.target, "Node", "name")), "Node name multiplicities must match expected Tree labels");
        assertEquals(counts(expectedEdges), counts(edgePairs(run.target)), "Edge multiplicities must match expected source->target Node names");
        assertEquals(expectedNodes.size(), allOfType(run.target, "Node").size(), "No superfluous or missing Nodes");
        assertEquals(expectedEdges.size(), allOfType(run.target, "Edge").size(), "No superfluous or missing Edges");
    }

    private RunResult runTransformation(String inputModel) throws Exception {
        EmfModel source = createEmfModel("Tree", inputModel, "Tree", true, false);
        File targetFile = File.createTempFile("tree2graph_generated_", ".model");
        targetFile.deleteOnExit();
        EmfModel target = createEmfModelFromFile("Graph", targetFile.getAbsolutePath(), "Graph", false, true);
        runEtl(ETL, source, target);
        return new RunResult(source, target);
    }

    private List<String> namesOf(EmfModel model, String typeName, String featureName) throws Exception {
        List<String> names = new ArrayList<>();
        for (EObject object : allOfType(model, typeName)) {
            names.add(stringFeature(object, featureName));
        }
        return names;
    }

    private List<String> edgePairs(EmfModel model) throws Exception {
        List<String> pairs = new ArrayList<>();
        for (EObject edge : allOfType(model, "Edge")) {
            EObject source = reference(edge, "source");
            EObject target = reference(edge, "target");
            assertNotNull(source, "Edge.source must be set");
            assertNotNull(target, "Edge.target must be set");
            pairs.add(stringFeature(source, "name") + "->" + stringFeature(target, "name"));
        }
        return pairs;
    }

    private Map<String, Integer> counts(Collection<String> values) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (String value : values) {
            counts.put(value, counts.getOrDefault(value, 0) + 1);
        }
        return counts;
    }

    private Collection<EObject> allOfType(EmfModel model, String typeName) throws Exception {
        Collection<?> values = model.getAllOfType(typeName);
        Collection<EObject> result = new ArrayList<>();
        for (Object value : values) {
            result.add((EObject) value);
        }
        return result;
    }

    private String stringFeature(EObject object, String featureName) {
        Object value = object.eGet(object.eClass().getEStructuralFeature(featureName));
        return value == null ? null : String.valueOf(value);
    }

    private EObject reference(EObject object, String featureName) {
        return (EObject) object.eGet(object.eClass().getEStructuralFeature(featureName));
    }

    private static final class RunResult {
        final EmfModel source;
        final EmfModel target;

        RunResult(EmfModel source, EmfModel target) {
            this.source = source;
            this.target = target;
        }
    }
}
