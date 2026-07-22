```java
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.io.File;
import java.util.List;

public class GeneratedTree2GraphSemanticTest {

    private Tree treeModel;
    private Graph graphModel;

    @BeforeEach
    public void setUp() {
        // Load the models here
        treeModel = loadModel("tree_simple.model");
        graphModel = transformTreeToGraph(treeModel);
    }

    @Test
    public void testNodeCorrespondence() {
        List<Node> graphNodes = graphModel.getNodes();
        for (Node node : graphNodes) {
            assertTrue(findTreeNodeWithLabel(treeModel, node.getName()) != null);
        }
    }

    @Test
    public void testNameMatching() {
        List<Node> graphNodes = graphModel.getNodes();
        for (Node node : graphNodes) {
            TreeNode treeNode = findTreeNodeWithLabel(treeModel, node.getName());
            assertNotNull(treeNode);
            assertEquals(node.getName(), treeNode.getLabel());
        }
    }

    @Test
    public void testParentChildRelationships() {
        List<Node> graphNodes = graphModel.getNodes();
        for (Node node : graphNodes) {
            if (!node.getIncoming().isEmpty()) {
                Node parentNode = node.getIncoming().get(0).getSource();
                TreeNode parentTreeNode = findTreeNodeWithLabel(treeModel, parentNode.getName());
                assertNotNull(parentTreeNode);
                assertTrue(parentTreeNode.getChildren().contains(findTreeNodeWithLabel(treeModel, node.getName())));
            }
        }
    }

    @Test
    public void testNoSuperfluousNodesOrEdges() {
        List<Node> graphNodes = graphModel.getNodes();
        for (Node node : graphNodes) {
            TreeNode treeNode = findTreeNodeWithLabel(treeModel, node.getName());
            assertNotNull(treeNode);
            assertEquals(node.getIncoming().size(), treeNode.getParents().size());
            assertEquals(node.getOutgoing().size(), treeNode.getChildren().size());
        }
    }

    private Tree loadModel(String fileName) {
        // Implement model loading logic here
        return null;
    }

    private Graph transformTreeToGraph(Tree treeModel) {
        // Implement transformation logic here
        return new Graph();
    }

    private TreeNode findTreeNodeWithLabel(Tree tree, String label) {
        if (tree.getLabel().equals(label)) {
            return new TreeNode(tree);
        }
        for (Tree child : tree.getChildren()) {
            TreeNode result = findTreeNodeWithLabel(child, label);
            if (result != null) {
                return result;
            }
        }
        return null;
    }

    private static class Tree {
        private String label;
        private List<Tree> children;

        // Getters and setters
    }

    private static class TreeNode {
        private String label;
        private List<TreeNode> parents;
        private List<TreeNode> children;

        public TreeNode(Tree tree) {
            this.label = tree.getLabel();
            this.parents = tree.getParent() != null ? List.of(new TreeNode(tree.getParent())) : List.of();
            this.children = tree.getChildren().stream().map(TreeNode::new).toList();
        }

        // Getters and setters
    }

    private static class Graph {
        private List<Node> nodes;

        public List<Node> getNodes() {
            return nodes;
        }
    }

    private static class Node {
        private String name;
        private List<Edge> incoming;
        private List<Edge> outgoing;

        public String getName() {
            return name;
        }

        public List<Edge> getIncoming() {
            return incoming;
        }

        public List<Edge> getOutgoing() {
            return outgoing;
        }
    }

    private static class Edge {
        private Node source;
        private Node target;

        public Node getSource() {
            return source;
        }

        public Node getTarget() {
            return target;
        }
    }
}
```

```xml
<!-- tree_simple.model -->
<Tree label="Root">
  <children>
    <Tree label="Child1"/>
    <Tree label="Child2"/>
  </children>
</Tree>

<!-- tree_branching.model -->
<Tree label="Root">
  <children>
    <Tree label="Child1">
      <children>
        <Tree label="Grandchild1"/>
        <Tree label="Grandchild2"/>
      </children>
    </Tree>
    <Tree label="Child2"/>
  </children>
</Tree>

<!-- tree_deep.model -->
<Tree label="Root">
  <children>
    <Tree label="Child1">
      <children>
        <Tree label="Grandchild1">
          <children>
            <Tree label="GreatGrandchild1"/>
            <Tree label="GreatGrandchild2"/>
          </children>
        </Tree>
        <Tree label="Grandchild2"/>
      </children>
    </Tree>
    <Tree label="Child2"/>
  </children>
</Tree>
```