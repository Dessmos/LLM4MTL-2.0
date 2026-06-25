```java
/**
 * GeneratedTree2GraphSemanticTest.java
 */
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.util.List;

public class GeneratedTree2GraphSemanticTest {

    @Test
    public void testSimpleTreeTransformation() {
        // Load the tree_simple.model file and perform transformation
        Tree tree = loadModel("tree_simple.model");
        Graph graph = transformToGraph(tree);

        // Assert that nodes are created for each tree node
        assertEquals(3, graph.getNodes().size());

        // Verify that node names are preserved during transformation
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Node1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Node2".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Node3".equals(node.getName())));

        // Confirm that graph edges are created for parent-child relations in the tree
        assertEquals(2, graph.getNodes().get(0).getOutgoing().size());
        assertEquals(1, graph.getNodes().get(1).getIncoming().size());

        // Check for no superfluous nodes or edges in the resulting graph
        assertTrue(graph.getNodes().stream()
                .noneMatch(node -> node.getName().equals("Node4")));
    }

    @Test
    public void testBranchingTreeTransformation() {
        // Load the tree_branching.model file and perform transformation
        Tree tree = loadModel("tree_branching.model");
        Graph graph = transformToGraph(tree);

        // Assert that nodes are created for each tree node
        assertEquals(5, graph.getNodes().size());

        // Verify that node names are preserved during transformation
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Root".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Child1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Child2".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Grandchild1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Grandchild2".equals(node.getName())));

        // Confirm that graph edges are created for parent-child relations in the tree
        assertEquals(3, graph.getNodes().get(0).getOutgoing().size());
        assertEquals(1, graph.getNodes().get(1).getIncoming().size());
        assertEquals(1, graph.getNodes().get(2).getIncoming().size());
        assertEquals(1, graph.getNodes().get(3).getIncoming().size());
        assertEquals(1, graph.getNodes().get(4).getIncoming().size());

        // Check for no superfluous nodes or edges in the resulting graph
        assertTrue(graph.getNodes().stream()
                .noneMatch(node -> node.getName().equals("Grandchild3")));
    }

    @Test
    public void testDeepTreeTransformation() {
        // Load the tree_deep.model file and perform transformation
        Tree tree = loadModel("tree_deep.model");
        Graph graph = transformToGraph(tree);

        // Assert that nodes are created for each tree node
        assertEquals(10, graph.getNodes().size());

        // Verify that node names are preserved during transformation
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Root".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Child1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Child2".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Grandchild1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "Grandchild2".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "GreatGrandchild1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "GreatGrandchild2".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "GreatGreatGrandchild1".equals(node.getName())));
        assertTrue(graph.getNodes().stream()
                .anyMatch(node -> "GreatGreatGrandchild2".equals(node.getName())));

        // Confirm that graph edges are created for parent-child relations in the tree
        assertEquals(3, graph.getNodes().get(0).getOutgoing().size());
        assertEquals(1, graph.getNodes().get(1).getIncoming().size());
        assertEquals(1, graph.getNodes().get(2).getIncoming().size());
        assertEquals(1, graph.getNodes().get(3).getIncoming().size());
        assertEquals(1, graph.getNodes().get(4).getIncoming().size());
        assertEquals(1, graph.getNodes().get(5).getIncoming().size());
        assertEquals(1, graph.getNodes().get(6).getIncoming().size());
        assertEquals(1, graph.getNodes().get(7).getIncoming().size());

        // Check for no superfluous nodes or edges in the resulting graph
        assertTrue(graph.getNodes().stream()
                .noneMatch(node -> node.getName().equals("GreatGreatGrandchild3")));
    }

    private Tree loadModel(String filename) {
        // Implement model loading logic here
        return new Tree(); // Placeholder
    }

    private Graph transformToGraph(Tree tree) {
        // Implement transformation logic here
        return new Graph(); // Placeholder
    }
}
```

```xml
<!-- tree_simple.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Node1"/>
    <Tree:Tree label="Node2"/>
    <Tree:Tree label="Node3"/>
  </children>
</Tree:Tree>

<!-- tree_branching.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Child1">
      <children>
        <Tree:Tree label="Grandchild1"/>
        <Tree:Tree label="Grandchild2"/>
      </children>
    </Tree:Tree>
    <Tree:Tree label="Child2"/>
  </children>
</Tree:Tree>

<!-- tree_deep.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Child1">
      <children>
        <Tree:Tree label="Grandchild1">
          <children>
            <Tree:Tree label="GreatGrandchild1"/>
            <Tree:Tree label="GreatGrandchild2"/>
          </children>
        </Tree:Tree>
        <Tree:Tree label="Grandchild2">
          <children>
            <Tree:Tree label="GreatGrandchild3"/>
          </children>
        </Tree:Tree>
      </children>
    </Tree:Tree>
    <Tree:Tree label="Child2"/>
  </children>
</Tree:Tree>
```