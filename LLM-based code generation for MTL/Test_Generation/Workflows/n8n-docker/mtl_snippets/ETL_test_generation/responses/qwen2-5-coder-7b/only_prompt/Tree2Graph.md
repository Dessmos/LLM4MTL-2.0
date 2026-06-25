```java
/**
 * Developer Prompt: Create an executable Java/JUnit semantic test suite for Tree2Graph.
 *
 * Requirements:
 * 1. The test suite must be contained in the file GeneratedTree2GraphSemanticTest.java.
 * 2. Three model files are required: tree_simple.model, tree_branching.model, and tree_deep.model.
 * 3. The tests should not depend on manual Tree2GraphTest.
 * 4. Generated tests become the semantic oracle only after technical and reference validation.
 *
 * Test Suite Requirements:
 * - Assertions for graph node creation
 * - Assertions for node name preservation
 * - Assertions for graph edge creation for parent-child relations
 * - Assertions for correct edge endpoints
 * - Assertions to ensure no superfluous nodes or edges are created
 */

// GeneratedTree2GraphSemanticTest.java

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeneratedTree2GraphSemanticTest {

    @Test
    public void testSimpleTree() {
        // Load tree_simple.model and perform transformation
        Graph graph = transformModel("tree_simple.model");
        
        assertEquals(2, graph.getNodes().size(), "There should be 2 nodes in the graph.");
        
        Node rootNode = findNodeByName(graph, "root");
        assertNotNull(rootNode, "Root node should exist.");
        assertEquals("root", rootNode.getName(), "Root node name should be preserved.");
        
        Node childNode = findNodeByName(graph, "child");
        assertNotNull(childNode, "Child node should exist.");
        assertEquals("child", childNode.getName(), "Child node name should be preserved.");
        
        assertTrue(rootNode.getOutgoing().contains(childNode), "Edge from root to child should exist.");
        assertTrue(childNode.getIncoming().contains(rootNode), "Edge from child to root should exist.");
    }

    @Test
    public void testBranchingTree() {
        // Load tree_branching.model and perform transformation
        Graph graph = transformModel("tree_branching.model");
        
        assertEquals(5, graph.getNodes().size(), "There should be 5 nodes in the graph.");
        
        Node rootNode = findNodeByName(graph, "root");
        assertNotNull(rootNode, "Root node should exist.");
        assertEquals("root", rootNode.getName(), "Root node name should be preserved.");
        
        Node child1Node = findNodeByName(graph, "child1");
        assertNotNull(child1Node, "Child1 node should exist.");
        assertEquals("child1", child1Node.getName(), "Child1 node name should be preserved.");
        
        Node child2Node = findNodeByName(graph, "child2");
        assertNotNull(child2Node, "Child2 node should exist.");
        assertEquals("child2", child2Node.getName(), "Child2 node name should be preserved.");
        
        Node grandChild1Node = findNodeByName(graph, "grandChild1");
        assertNotNull(grandChild1Node, "GrandChild1 node should exist.");
        assertEquals("grandChild1", grandChild1Node.getName(), "GrandChild1 node name should be preserved.");
        
        assertTrue(rootNode.getOutgoing().contains(child1Node), "Edge from root to child1 should exist.");
        assertTrue(rootNode.getOutgoing().contains(child2Node), "Edge from root to child2 should exist.");
        assertTrue(child1Node.getOutgoing().contains(grandChild1Node), "Edge from child1 to grandChild1 should exist.");
        
        assertTrue(child1Node.getIncoming().contains(rootNode), "Edge from child1 to root should exist.");
        assertTrue(child2Node.getIncoming().contains(rootNode), "Edge from child2 to root should exist.");
        assertTrue(grandChild1Node.getIncoming().contains(child1Node), "Edge from grandChild1 to child1 should exist.");
    }

    @Test
    public void testDeepTree() {
        // Load tree_deep.model and perform transformation
        Graph graph = transformModel("tree_deep.model");
        
        assertEquals(8, graph.getNodes().size(), "There should be 8 nodes in the graph.");
        
        Node rootNode = findNodeByName(graph, "root");
        assertNotNull(rootNode, "Root node should exist.");
        assertEquals("root", rootNode.getName(), "Root node name should be preserved.");
        
        Node child1Node = findNodeByName(graph, "child1");
        assertNotNull(child1Node, "Child1 node should exist.");
        assertEquals("child1", child1Node.getName(), "Child1 node name should be preserved.");
        
        Node child2Node = findNodeByName(graph, "child2");
        assertNotNull(child2Node, "Child2 node should exist.");
        assertEquals("child2", child2Node.getName(), "Child2 node name should be preserved.");
        
        Node grandChild1Node = findNodeByName(graph, "grandChild1");
        assertNotNull(grandChild1Node, "GrandChild1 node should exist.");
        assertEquals("grandChild1", grandChild1Node.getName(), "GrandChild1 node name should be preserved.");
        
        Node grandChild2Node = findNodeByName(graph, "grandChild2");
        assertNotNull(grandChild2Node, "GrandChild2 node should exist.");
        assertEquals("grandChild2", grandChild2Node.getName(), "GrandChild2 node name should be preserved.");
        
        Node greatGrandChild1Node = findNodeByName(graph, "greatGrandChild1");
        assertNotNull(greatGrandChild1Node, "GreatGrandChild1 node should exist.");
        assertEquals("greatGrandChild1", greatGrandChild1Node.getName(), "GreatGrandChild1 node name should be preserved.");
        
        assertTrue(rootNode.getOutgoing().contains(child1Node), "Edge from root to child1 should exist.");
        assertTrue(rootNode.getOutgoing().contains(child2Node), "Edge from root to child2 should exist.");
        assertTrue(child1Node.getOutgoing().contains(grandChild1Node), "Edge from child1 to grandChild1 should exist.");
        assertTrue(child1Node.getOutgoing().contains(grandChild2Node), "Edge from child1 to grandChild2 should exist.");
        assertTrue(grandChild1Node.getOutgoing().contains(greatGrandChild1Node), "Edge from grandChild1 to greatGrandChild1 should exist.");
        
        assertTrue(child1Node.getIncoming().contains(rootNode), "Edge from child1 to root should exist.");
        assertTrue(child2Node.getIncoming().contains(rootNode), "Edge from child2 to root should exist.");
        assertTrue(grandChild1Node.getIncoming().contains(child1Node), "Edge from grandChild1 to child1 should exist.");
        assertTrue(grandChild2Node.getIncoming().contains(child1Node), "Edge from grandChild2 to child1 should exist.");
        assertTrue(greatGrandChild1Node.getIncoming().contains(grandChild1Node), "Edge from greatGrandChild1 to grandChild1 should exist.");
    }

    private Graph transformModel(String modelName) {
        // Placeholder for model transformation logic
        // This method should load the model, perform the Tree2Graph transformation, and return the resulting Graph object
        throw new UnsupportedOperationException("Model transformation logic not implemented");
    }

    private Node findNodeByName(Graph graph, String name) {
        for (Node node : graph.getNodes()) {
            if (node.getName().equals(name)) {
                return node;
            }
        }
        return null;
    }
}
```

**Model Files:**
- **tree_simple.model**: A simple tree with a single root node and one child.
```xml
<Tree:Tree label="root">
  <Tree:children>
    <Tree:Tree label="child"/>
  </Tree:children>
</Tree:Tree>
```

- **tree_branching.model**: A tree with multiple branches and children at different levels.
```xml
<Tree:Tree label="root">
  <Tree:children>
    <Tree:Tree label="child1">
      <Tree:children>
        <Tree:Tree label="grandChild1"/>
      </Tree:children>
    </Tree:Tree>
    <Tree:Tree label="child2">
      <Tree:children>
        <Tree:Tree label="grandChild2"/>
      </Tree:children>
    </Tree:Tree>
  </Tree:children>
</Tree:Tree>
```

- **tree_deep.model**: A deeply nested tree to test the transformation of complex structures.
```xml
<Tree:Tree label="root">
  <Tree:children>
    <Tree:Tree label="child1">
      <Tree:children>
        <Tree:Tree label="grandChild1">
          <Tree:children>
            <Tree:Tree label="greatGrandChild1"/>
          </Tree:children>
        </Tree:Tree>
        <Tree:Tree label="grandChild2"/>
      </Tree:children>
    </Tree:Tree>
  </Tree:children>
</Tree:Tree>
```