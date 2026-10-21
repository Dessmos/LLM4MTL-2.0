# Reactions Language Parser

This Maven module generates a standalone (shaded) Java archive capable of parsing and validating source files written in the **Reactions Language**, a domain‑specific language for model synchronisation.

## Prerequisites

- Java 17 or later
- Maven 3.8 or later

## Building the parser

Compile and package the parser using:

```sh
mvn clean package
```

The resulting shaded JAR will be created under the `target/` directory (for example `reactions-language-parser-<version>-shaded.jar`).  The shading process bundles all dependencies so the parser can be run without additional libraries.

## Usage

You can use the shaded JAR to check the syntax of a `.reactions` file from the command line:

```sh
java -jar reactions-parser-0.1.0-SNAPSHOT-all.jar <input.reactions> <output.xmi> [<ecoreDir>]
```

If the file contains syntax errors, the parser prints diagnostics and returns a non‑zero exit code.

## Status

This parser module is a proof of concept; the grammar may not yet cover the entire Reactions Language.  Contributions and bug reports are welcome.