Make the line between fix and LLM-generated.

Example of a contract: (from benchmark/tasks/etl/task_contracts/Tree2Graph.json)

{
  "task": "Tree2Graph",
  "transformation": "Tree2Graph.etl",
  "reference": "benchmark/tasks/etl/references/Tree2Graph.etl",
  "sourceHash": "9c0f62b7...",
  "models": [
    { "runtimeName": "Graph", "roles": ["target"], "kind": "emf",
      "metamodelUri": "Graph", "metamodelNsPrefix": "Graph",
      "metamodelFile": "benchmark/metamodels/.../Graph.ecore",
      "typesUsedInTransformation": ["Edge", "Node"],
      "availableTypes": ["Graph", "Node", "Edge"] }
  ]
}

The LLM only supplies semantics (input models and expected target-model facts), while this layer rewrites the bindings from the source of truth.

models.py       - style of a contract
loadre.py       - reads from the local store
enforcement.py  - checks if LLM calls for "new" metamodel, sets real URI
render.py       - the same contract in .nd style, so developer can read easier
build_language_task_contracts.py - generator of contracts, from oracle and .ecore files
