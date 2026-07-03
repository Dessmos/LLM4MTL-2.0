package org.example.etl;

import static org.junit.jupiter.api.Assertions.*;

import java.util.*;
import java.util.stream.Collectors;

import org.eclipse.emf.common.util.EList;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.eol.models.IModel;
import org.junit.jupiter.api.Test;

/**
 * Semantic test suite for Tree2Graph.etl.
 * 
 * This suite is self-contained and does not depend on any manually written semantic tests.
 */
public class Tree2GraphSemanticTest extends EtlTestBase {

    private static final String TREE_MM = "src/test/resources/metamodels/Tree.ecore";
    private static final String GRAPH_MM = "src/test/resources/metamodels/Graph.ecore";
    private static final String ETL = "src/main/etl/Tree2Graph.etl";

    private static final String MODEL_SINGLE_ROOT = "src/test/resources/models/tree_single_root.xmi";
    private static final String MODEL_ROOT_ONE_CHILD = "src/test/resources/models/tree_root_one_child.xmi";
    private static final String MODEL_DEEP = "src/test/resources/models/tree_deep_chain.xmi";
    private static final String MODEL_BRANCHING = "src/test/resources/models/tree_branching.xmi";
    private static final String MODEL_LABELS = "src/test/resources/models/tree_distinct_labels.xmi";

    @Test
    public void singleRoot_only_oneNode_noEdges_nameCopied() throws Exception {
        TransformationRun run = runTransformation(MODEL_SINGLE_ROOT);

        List<EObject> trees = allOfType(run.source, "Tree");
        List<EObject> nodes = allOfType(run.target, "Node");
        List<EObject> edges = allOfType(run.target, "Edge");

        assertEquals(1, trees.size(), "Sanity: source must contain exactly one Tree");
        assertEquals(1, nodes.size(), "Exactly one Node per Tree");
        assertEquals(0, edges.size(), "Root node should not produce an Edge");

        String label = stringAttr(trees.get(0), "label");
        String name = stringAttr(nodes.get(0), "name");
        assertEquals(label, name, "Node.name must equal Tree.label");
    }

    @Test
    public void rootWithOneChild_twoNodes_oneEdge_rootToChild() throws Exception {
        TransformationRun run = runTransformation(MODEL_ROOT_ONE_CHILD);

        List<EObject> trees = allOfType(run.source, "Tree");
        List<EObject> nodes = allOfType(run.target, "Node");
        List<EObject> edges = allOfType(run.target, "Edge");

        assertEquals(2, trees.size(), "Sanity: source must contain root + child");
        assertEquals(2, nodes.size(), "Exactly one Node per Tree");
        assertEquals(1, edges.size(), "Exactly one Edge for the single non-root Tree");

        Map<String, EObject> nodeByName = nodes.stream()
            .collect(Collectors.toMap(n -> stringAttr(n, "name"), n -> n));

        assertTrue(nodeByName.containsKey("root"));
        assertTrue(nodeByName.containsKey("child"));

        EObject edge = edges.get(0);
        EObject source = ref(edge, "source");
        EObject target = ref(edge, "target");

        assertSame(nodeByName.get("root"), source, "Edge source must be transformed parent Node");
        assertSame(nodeByName.get("child"), target, "Edge target must be transformed child Node");
    }

    @Test
    public void deeperHierarchy_edgeCountEqualsNonRoot_andDirectionsCorrect() throws Exception {
        TransformationRun run = runTransformation(MODEL_DEEP);

        List<EObject> trees = allOfType(run.source, "Tree");
        List<EObject> nodes = allOfType(run.target, "Node");
        List<EObject> edges = allOfType(run.target, "Edge");

        long nonRoots = trees.stream().filter(t -> ref(t, "parent") != null).count();

        assertEquals(trees.size(), nodes.size(), "Exactly one Node per Tree");
        assertEquals(nonRoots, edges.size(), "Exactly one Edge per non-root Tree");

        Map<String, EObject> nodeByName = nodes.stream()
            .collect(Collectors.toMap(n -> stringAttr(n, "name"), n -> n));

        Set<String> directed = edges.stream()
            .map(e -> stringAttr(ref(e, "source"), "name") + "->" + stringAttr(ref(e, "target"), "name"))
            .collect(Collectors.toSet());

        assertEquals(Set.of("root->child", "child->grandchild"), directed, "All and only expected parent->child edges");
    }

    @Test
    public void branchingTree_allExpectedEdges_noUnexpectedEdges_noExtras() throws Exception {
        TransformationRun run = runTransformation(MODEL_BRANCHING);

        List<EObject> trees = allOfType(run.source, "Tree");
        List<EObject> nodes = allOfType(run.target, "Node");
        List<EObject> edges = allOfType(run.target, "Edge");

        assertEquals(trees.size(), nodes.size(), "No extra/missing Nodes");
        assertEquals(trees.size() - 1, edges.size(), "No extra/missing Edges for one-root tree");

        Set<String> expected = Set.of("root->a", "root->b", "root->c", "b->b1");
        Set<String> actual = edges.stream()
            .map(e -> stringAttr(ref(e, "source"), "name") + "->" + stringAttr(ref(e, "target"), "name"))
            .collect(Collectors.toSet());

        assertEquals(expected, actual, "Edges must be exactly expected parent-child links");

        Set<EObject> nodeSet = new HashSet<>(nodes);
        for (EObject e : edges) {
            assertTrue(nodeSet.contains(ref(e, "source")), "Edge.source must reference a transformed Node");
            assertTrue(nodeSet.contains(ref(e, "target")), "Edge.target must reference a transformed Node");
        }
    }

    @Test
    public void labelHandling_distinctLabels_areCopiedExactly() throws Exception {
        TransformationRun run = runTransformation(MODEL_LABELS);

        List<EObject> trees = allOfType(run.source, "Tree");
        List<EObject> nodes = allOfType(run.target, "Node");
        List<EObject> edges = allOfType(run.target, "Edge");

        assertEquals(trees.size(), nodes.size(), "One Node per Tree");
        assertEquals(trees.size() - 1, edges.size(), "One Edge per non-root node");

        Set<String> treeLabels = trees.stream().map(t -> stringAttr(t, "label")).collect(Collectors.toSet());
        Set<String> nodeNames = nodes.stream().map(n -> stringAttr(n, "name")).collect(Collectors.toSet());

        assertEquals(treeLabels, nodeNames, "Node names must exactly match tree labels");
        assertEquals(Set.of("ROOT_X", "left-1", "right_2", "leaf.Z"), nodeNames);
    }

    private TransformationRun runTransformation(String inputModel) throws Exception {
        IModel source = createEmfModel("Tree", inputModel, TREE_MM, true, false);
        IModel target = createEmfModel("Graph", "target/generated-" + UUID.randomUUID() + ".xmi", GRAPH_MM, false, true);

        executeEtl(ETL, source, target);
        return new TransformationRun(source, target);
    }

    private List<EObject> allOfType(IModel model, String typeName) throws Exception {
        List<?> all = model.getAllOfType(typeName);
        List<EObject> result = new ArrayList<>();
        for (Object o : all) result.add((EObject) o);
        return result;
    }

    private String stringAttr(EObject obj, String attr) {
        Object v = obj.eGet(obj.eClass().getEStructuralFeature(attr));
        return v == null ? null : v.toString();
    }

    private EObject ref(EObject obj, String refName) {
        Object v = obj.eGet(obj.eClass().getEStructuralFeature(refName));
        return (EObject) v;
    }

    @SuppressWarnings("unused")
    private EList<?> refs(EObject obj, String refName) {
        return (EList<?>) obj.eGet(obj.eClass().getEStructuralFeature(refName));
    }

    private static class TransformationRun {
        final IModel source;
        final IModel target;

        TransformationRun(IModel source, IModel target) {
            this.source = source;
            this.target = target;
        }
    }
}
