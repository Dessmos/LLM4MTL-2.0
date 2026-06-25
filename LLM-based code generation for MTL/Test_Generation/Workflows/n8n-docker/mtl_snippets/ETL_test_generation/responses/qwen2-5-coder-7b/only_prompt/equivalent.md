```java
public class GeneratedTree2GraphSemanticTest {

    @Test
    public void testSimpleTree() {
        // Load tree_simple.model
        TreeModel treeModel = loadModel("tree_simple.model");
        
        // Perform transformation
        GraphModel graphModel = transformToGraph(treeModel);
        
        // Assertions for simple tree structure
        assertEquals(2, graphModel.getNodes().size());
        assertNotNull(graphModel.findNodeByName("Root"));
        assertNotNull(graphModel.findNodeByName("Child"));
        assertNotNull(graphModel.findEdgeBetween("Root", "Child"));
    }

    @Test
    public void testBranchingTree() {
        // Load tree_branching.model
        TreeModel treeModel = loadModel("tree_branching.model");
        
        // Perform transformation
        GraphModel graphModel = transformToGraph(treeModel);
        
        // Assertions for branching tree structure
        assertEquals(4, graphModel.getNodes().size());
        assertNotNull(graphModel.findNodeByName("Root"));
        assertNotNull(graphModel.findNodeByName("Child1"));
        assertNotNull(graphModel.findNodeByName("Child2"));
        assertNotNull(graphModel.findEdgeBetween("Root", "Child1"));
        assertNotNull(graphModel.findEdgeBetween("Root", "Child2"));
    }

    @Test
    public void testDeepTree() {
        // Load tree_deep.model
        TreeModel treeModel = loadModel("tree_deep.model");
        
        // Perform transformation
        GraphModel graphModel = transformToGraph(treeModel);
        
        // Assertions for deep tree structure
        assertEquals(6, graphModel.getNodes().size());
        assertNotNull(graphModel.findNodeByName("Root"));
        assertNotNull(graphModel.findNodeByName("Child1"));
        assertNotNull(graphModel.findNodeByName("Grandchild1"));
        assertNotNull(graphModel.findEdgeBetween("Root", "Child1"));
        assertNotNull(graphModel.findEdgeBetween("Child1", "Grandchild1"));
    }

    private TreeModel loadModel(String modelName) {
        // Implementation to load model from file
        try (InputStream inputStream = getClass().getResourceAsStream("/" + modelName)) {
            return ModelLoader.load(inputStream);
        } catch (IOException e) {
            throw new RuntimeException("Failed to load model: " + modelName, e);
        }
    }

    private GraphModel transformToGraph(TreeModel treeModel) {
        // Implementation of the transformation logic
        Tree2Graph transformer = new Tree2Graph();
        return transformer.transform(treeModel);
    }
}
```

```xml
<!-- tree_simple.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Child"/>
  </children>
</Tree:Tree>
```

```xml
<!-- tree_branching.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Child1"/>
    <Tree:Tree label="Child2"/>
  </children>
</Tree:Tree>
```

```xml
<!-- tree_deep.model -->
<Tree:Tree label="Root">
  <children>
    <Tree:Tree label="Child1">
      <children>
        <Tree:Tree label="Grandchild1"/>
      </children>
    </Tree:Tree>
  </children>
</Tree:Tree>
```

### Notes:
- The `loadModel` method reads the model files from the classpath.
- The `transformToGraph` method uses a hypothetical `Tree2Graph` transformer to perform the transformation.
- Ensure that the `ModelLoader` and `Tree2Graph` classes are correctly implemented and available in your project.