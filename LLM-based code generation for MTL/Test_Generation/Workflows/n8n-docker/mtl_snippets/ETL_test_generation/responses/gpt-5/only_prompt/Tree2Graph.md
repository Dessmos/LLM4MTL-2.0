```java file=Tree2GraphSemanticTest.java
package org.eclipse.epsilon.examples.etl.generated;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.examples.etl.EtlTestBase;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Semantic oracle candidate for Tree2Graph.etl (rule Tree2Node).
 *
 * Expected semantics:
 * 1) For every Tree!Tree element, create one Graph!Node
 * 2) Node.name == Tree.label
 * 3) If Tree.parent is defined, create one edge from node(Tree) to node(Tree.parent)
 * 4) No superfluous nodes/edges
 *
 * This suite is self-contained and does not depend on any existing manual semantic tests.
 */
public class Tree2GraphSemanticTest extends EtlTestBase {

    private static final String ETL = "transformations/Tree2Graph.etl";
    private static final String TREE_MM = "metamodels/Tree.ecore";
    private static final String GRAPH_MM = "metamodels/Graph.ecore";

    private static final String MODEL_SINGLE_ROOT = "generated-models/tree2graph/tree_single_root.model";
    private static final String MODEL_CHAIN_3 = "generated-models/tree2graph/tree_chain_3.model";
    private static final String MODEL_BRANCHING = "generated-models/tree2graph/tree_branching.model";

    @BeforeEach
    public void setUp() throws Exception {
        registerMetamodel(TREE_MM);
        registerMetamodel(GRAPH_MM);
    }

    @Test
    public void singleRoot_createsOneNode_noEdges() throws Exception {
        var result = runTransformation(ETL, TREE_MM, GRAPH_MM, MODEL_SINGLE_ROOT);

        List<EObject> trees = allOfType(result.sourceModel, "Tree");
        List<EObject> nodes = allOfType(result.targetModel, "Node");
        List<EObject> edges = allOfType(result.targetModel, "Edge");

        assertEquals(1, trees.size(), "Exactly one source Tree expected");
        assertEquals(1, nodes.size(), "Exactly one Node should be created");
        assertEquals(0, edges.size(), "Root has no parent, therefore no edge");

        String treeLabel = asString(trees.get(0), "label");
        String nodeName = asString(nodes.get(0), "name");
        assertEquals(treeLabel, nodeName, "Node name must equal Tree label");
    }

    @Test
    public void chainOfThree_createsThreeNodes_andTwoEdgesToParent() throws Exception {
        var result = runTransformation(ETL, TREE_MM, GRAPH_MM, MODEL_CHAIN_3);

        List<EObject> trees = allOfType(result.sourceModel, "Tree");
        List<EObject> nodes = allOfType(result.targetModel, "Node");
        List<EObject> edges = allOfType(result.targetModel, "Edge");

        assertEquals(3, trees.size(), "Source must contain 3 Tree elements");
        assertEquals(3, nodes.size(), "One node per tree element");
        assertEquals(2, edges.size(), "Non-root nodes are 2 => exactly 2 edges");

        // label -> expected parent label (null for root)
        Map<String, String> expectedParentByLabel = expectedParentLabelByTreeLabel(trees);
        Map<String, EObject> nodeByName = nodes.stream()
            .collect(Collectors.toMap(n -> asString(n, "name"), n -> n));

        // exact names, no extras
        assertEquals(expectedParentByLabel.keySet(), nodeByName.keySet());

        // verify every non-root tree has exactly one outgoing edge from child node to parent node
        for (Map.Entry<String, String> e : expectedParentByLabel.entrySet()) {
            String childLabel = e.getKey();
            String parentLabel = e.getValue();
            EObject childNode = nodeByName.get(childLabel);

            List<EObject> outgoing = getRefs(childNode, "outgoing");
            if (parentLabel == null) {
                assertEquals(0, outgoing.size(), "Root node must have no outgoing edge to parent");
            } else {
                assertEquals(1, outgoing.size(), "Non-root node must have exactly one edge to its parent");
                EObject edge = outgoing.get(0);
                EObject target = getRef(edge, "target");
                assertNotNull(target);
                assertEquals(parentLabel, asString(target, "name"),
                    "Edge target must be node corresponding to Tree.parent");
            }
        }

        // no edge should originate from a root node
        Set<String> rootLabels = expectedParentByLabel.entrySet().stream()
            .filter(x -> x.getValue() == null).map(Map.Entry::getKey).collect(Collectors.toSet());
        for (EObject edge : edges) {
            EObject src = getRef(edge, "source");
            assertNotNull(src);
            assertFalse(rootLabels.contains(asString(src, "name")),
                "Root node must not be source of parent-edge");
        }
    }

    @Test
    public void branchingTree_createsExactNodes_andParentEdges_only() throws Exception {
        var result = runTransformation(ETL, TREE_MM, GRAPH_MM, MODEL_BRANCHING);

        List<EObject> trees = allOfType(result.sourceModel, "Tree");
        List<EObject> nodes = allOfType(result.targetModel, "Node");
        List<EObject> edges = allOfType(result.targetModel, "Edge");

        Map<String, String> expectedParentByLabel = expectedParentLabelByTreeLabel(trees);

        int expectedNodeCount = trees.size();
        int expectedEdgeCount = (int) expectedParentByLabel.values().stream().filter(Objects::nonNull).count();

        assertEquals(expectedNodeCount, nodes.size(), "No superfluous or missing nodes");
        assertEquals(expectedEdgeCount, edges.size(), "No superfluous or missing edges");

        Map<String, EObject> nodeByName = nodes.stream()
            .collect(Collectors.toMap(n -> asString(n, "name"), n -> n));
        assertEquals(expectedParentByLabel.keySet(), nodeByName.keySet(),
            "Node names must match exactly tree labels");

        // Verify each expected child->parent connection exists exactly once
        Set<String> actualPairs = new HashSet<>();
        for (EObject edge : edges) {
            EObject src = getRef(edge, "source");
            EObject tgt = getRef(edge, "target");
            assertNotNull(src);
            assertNotNull(tgt);
            actualPairs.add(asString(src, "name") + "->" + asString(tgt, "name"));
        }

        Set<String> expectedPairs = new HashSet<>();
        expectedParentByLabel.forEach((child, parent) -> {
            if (parent != null) expectedPairs.add(child + "->" + parent);
        });

        assertEquals(expectedPairs, actualPairs, "Edges must be exactly child->parent mappings");
    }

    // ---------- Helpers (reflection-based, robust to concrete model wrapper APIs) ----------

    private static class RunResult {
        EmfModel sourceModel;
        EmfModel targetModel;
    }

    private RunResult runTransformation(String etl, String sourceMm, String targetMm, String sourceModelPath) throws Exception {
        EmfModel src = createEmfModel("Tree", sourceModelPath, "Tree", true, false);

        File targetFile = File.createTempFile("tree2graph_generated_", ".model");
        targetFile.deleteOnExit();
        EmfModel trg = createEmfModelFromFile("Graph", targetFile.getAbsolutePath(), "Graph", false, true);

        runEtl(etl, src, trg);

        RunResult rr = new RunResult();
        rr.sourceModel = src;
        rr.targetModel = trg;
        return rr;
    }

    private List<EObject> allOfType(EmfModel model, String typeName) throws Exception {
        Collection<?> values = model.getAllOfType(typeName);
        List<EObject> result = new ArrayList<>();
        for (Object value : values) {
            result.add((EObject) value);
        }
        return result;
    }

    private EObject getRef(EObject obj, String feature) {
        return (EObject) obj.eGet(obj.eClass().getEStructuralFeature(feature));
    }

    @SuppressWarnings("unchecked")
    private List<EObject> getRefs(EObject obj, String feature) {
        Object v = obj.eGet(obj.eClass().getEStructuralFeature(feature));
        if (v == null) return Collections.emptyList();
        return (List<EObject>) v;
    }

    private String asString(EObject obj, String feature) {
        Object v = obj.eGet(obj.eClass().getEStructuralFeature(feature));
        return v == null ? null : String.valueOf(v);
    }

    private Map<String, String> expectedParentLabelByTreeLabel(List<EObject> trees) {
        Map<EObject, String> labelByTree = new HashMap<>();
        for (EObject t : trees) labelByTree.put(t, asString(t, "label"));

        Map<String, String> expected = new HashMap<>();
        for (EObject t : trees) {
            String childLabel = labelByTree.get(t);
            EObject parent = (EObject) t.eGet(t.eClass().getEStructuralFeature("parent"));
            expected.put(childLabel, parent == null ? null : labelByTree.get(parent));
        }
        return expected;
    }
}
```

```xml file=models/tree_single_root.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root"/>
```

```xml file=models/tree_chain_3.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="n1">
  <children label="n2">
    <children label="n3"/>
  </children>
</Tree:Tree>
```

```xml file=models/tree_branching.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="r">
  <children label="a">
    <children label="a1"/>
    <children label="a2"/>
  </children>
  <children label="b"/>
  <children label="c">
    <children label="c1"/>
  </children>
</Tree:Tree>
```
