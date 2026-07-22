```java
/**
 * GeneratedTree2GraphSemanticTest.java
 */
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.io.File;
import java.util.List;

public class GeneratedTree2GraphSemanticTest {

    @Test
    public void testSimpleTreeTransformation() {
        // Load the model file
        File treeModelFile = new File("tree_simple.model");
        
        // Perform transformation (assuming a method exists to perform this)
        Graph graph = Tree2Graph.transform(treeModelFile);
        
        // Assertions for graph node creation
        assertEquals(1, graph.getNodes().size(), "There should be one node in the graph.");
        
        // Assertions to ensure node names are preserved from the source model
        Node rootNode = graph.getNodes().get(0);
        assertEquals("root", rootNode.getName(), "Node name should match the tree label.");
        
        // Assertions for no superfluous nodes or edges in the generated graph
        assertTrue(rootNode.getIncoming().isEmpty(), "Root node should have no incoming edges.");
        assertTrue(rootNode.getOutgoing().isEmpty(), "Root node should have no outgoing edges.");
    }

    @Test
    public void testBranchingTreeTransformation() {
        // Load the model file
        File treeModelFile = new File("tree_branching.model");
        
        // Perform transformation (assuming a method exists to perform this)
        Graph graph = Tree2Graph.transform(treeModelFile);
        
        // Assertions for graph node creation
        assertEquals(3, graph.getNodes().size(), "There should be three nodes in the graph.");
        
        // Assertions to ensure node names are preserved from the source model
        Node rootNode = graph.getNodes().get(0);
        assertEquals("root", rootNode.getName(), "Root node name should match the tree label.");
        
        Node childNode1 = graph.getNodes().get(1);
        assertEquals("child1", childNode1.getName(), "Child1 node name should match the tree label.");
        
        Node childNode2 = graph.getNodes().get(2);
        assertEquals("child2", childNode2.getName(), "Child2 node name should match the tree label.");
        
        // Assertions for graph edge creation representing parent-child relations
        assertEquals(2, rootNode.getOutgoing().size(), "Root node should have two outgoing edges.");
        assertTrue(rootNode.getOutgoing().stream()
            .anyMatch(edge -> edge.getTarget() == childNode1));
        assertTrue(rootNode.getOutgoing().stream()
            .anyMatch(edge -> edge.getTarget() == childNode2));
        
        // Assertions to verify correct edge endpoints (source and target nodes)
        assertEquals(0, childNode1.getIncoming().size(), "Child1 node should have no incoming edges.");
        assertEquals(1, childNode1.getOutgoing().size(), "Child1 node should have one outgoing edge.");
        assertEquals(rootNode, childNode1.getOutgoing().get(0).getSource());
        
        assertEquals(0, childNode2.getIncoming().size(), "Child2 node should have no incoming edges.");
        assertEquals(1, childNode2.getOutgoing().size(), "Child2 node should have one outgoing edge.");
        assertEquals(rootNode, childNode2.getOutgoing().get(0).getSource());
        
        // Assertions for no superfluous nodes or edges in the generated graph
        assertTrue(childNode1.getIncoming().isEmpty(), "Child1 node should have no incoming edges.");
        assertTrue(childNode2.getIncoming().isEmpty(), "Child2 node should have no incoming edges.");
    }

    @Test
    public void testDeepTreeTransformation() {
        // Load the model file
        File treeModelFile = new File("tree_deep.model");
        
        // Perform transformation (assuming a method exists to perform this)
        Graph graph = Tree2Graph.transform(treeModelFile);
        
        // Assertions for graph node creation
        assertEquals(4, graph.getNodes().size(), "There should be four nodes in the graph.");
        
        // Assertions to ensure node names are preserved from the source model
        Node rootNode = graph.getNodes().get(0);
        assertEquals("root", rootNode.getName(), "Root node name should match the tree label.");
        
        Node childNode1 = graph.getNodes().get(1);
        assertEquals("child1", childNode1.getName(), "Child1 node name should match the tree label.");
        
        Node childNode2 = graph.getNodes().get(2);
        assertEquals("child2", childNode2.getName(), "Child2 node name should match the tree label.");
        
        Node grandChildNode = graph.getNodes().get(3);
        assertEquals("grandchild", grandChildNode.getName(), "Grandchild node name should match the tree label.");
        
        // Assertions for graph edge creation representing parent-child relations
        assertEquals(2, rootNode.getOutgoing().size(), "Root node should have two outgoing edges.");
        assertTrue(rootNode.getOutgoing().stream()
            .anyMatch(edge -> edge.getTarget() == childNode1));
        assertTrue(rootNode.getOutgoing().stream()
            .anyMatch(edge -> edge.getTarget() == childNode2));
        
        assertEquals(1, childNode1.getOutgoing().size(), "Child1 node should have one outgoing edge.");
        assertEquals(grandChildNode, childNode1.getOutgoing().get(0).getTarget());
        
        // Assertions to verify correct edge endpoints (source and target nodes)
        assertEquals(0, childNode2.getIncoming().size(), "Child2 node should have no incoming edges.");
        assertEquals(1, childNode2.getOutgoing().size(), "Child2 node should have one outgoing edge.");
        assertEquals(rootNode, childNode2.getOutgoing().get(0).getSource());
        
        assertEquals(0, grandChildNode.getIncoming().size(), "Grandchild node should have no incoming edges.");
        assertEquals(1, grandChildNode.getOutgoing().size(), "Grandchild node should have one outgoing edge.");
        assertEquals(childNode1, grandChildNode.getOutgoing().get(0).getSource());
        
        // Assertions for no superfluous nodes or edges in the generated graph
        assertTrue(grandChildNode.getIncoming().isEmpty(), "Grandchild node should have no incoming edges.");
    }
}
```

```xml
<!-- tree_simple.model -->
<Tree:Tree label="root"/>

<!-- tree_branching.model -->
<Tree:Tree label="root">
  <children>
    <Tree:Tree label="child1"/>
    <Tree:Tree label="child2"/>
  </children>
</Tree:Tree>

<!-- tree_deep.model -->
<Tree:Tree label="root">
  <children>
    <Tree:Tree label="child1">
      <children>
        <Tree:Tree label="grandchild"/>
      </children>
    </Tree:Tree>
    <Tree:Tree label="child2"/>
  </children>
</Tree:Tree>
```