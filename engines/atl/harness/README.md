# ATL Tests

This module contains example transformations written in the **ATLAS Transformation Language (ATL)** and corresponding JUnit tests.  The examples illustrate how to convert models between different metamodels (for instance mapping Amalthea tasks to ASCET tasks, mapping family members to persons, and converting network structures to graphs).

## Structure

- `src/main/atl/` – ATL modules (`*.atl`) that implement the model transformations.  Each transformation defines matched rules and helpers to map concepts between source and target metamodels.
- `src/test/java/` – JUnit test cases that execute the ATL transformations and verify structural and semantic properties of the generated models.

## Building and running

Use Maven to compile the ATL modules and run the tests:

```sh
mvn clean test
```

The tests load the input models, run the ATL transformation via the Eclipse ATL engine and then assert that the output models meet the expected conditions (for example that elements have been created and attributes mapped correctly).

Consult the test classes for details on how each scenario is configured.