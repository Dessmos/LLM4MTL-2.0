# Reactions Language Tests

This project demonstrates how to implement model synchronisation and consistency preservation using the **Reactions Language**.  It is based on the Vitruv Methodologist template and showcases how a Virtual Single Underlying Model (V‑SUM) can be used to keep multiple views of a model in sync.

## Structure

The main subdirectories are:

- **model/** – contains the metamodel definition (an `.ecore` file).  When working outside of Eclipse, provide a corresponding `.genmodel` to enable code generation.
- **consistency/** – holds the consistency specifications written in the Reactions Language.  These include reaction files defining how changes in one model are propagated to another.
- **viewtype/** – defines the view types that describe how the V‑SUM is partitioned into separate views.  These are required to create and navigate the views.
- **vsum/** – contains the implementation of the V‑SUM itself along with helper classes used by the tests.

## Building and running the tests

Compile and run the unit tests with Maven:

```sh
mvn clean verify
```

The tests instantiate the V‑SUM, apply changes to one view and verify that the reactions update the other view accordingly.  They also test for deletions, updates and the creation of correspondence links.

If Maven fails to clean the project due to locked files, use the provided `cleanup.bat` script or manually remove all `target` directories.

## Additional resources

The Vitruv project provides further documentation on building and configuring projects:

- Maven build parent project – <https://github.com/vitruv-tools/Maven-Build-Parent/blob/main/readme.md>
- EMF template – <https://github.com/vitruv-tools/EMF-Template/blob/main/readme.md>

Refer to these pages for guidance on extending the tests or integrating additional metamodels.