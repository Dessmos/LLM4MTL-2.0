# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Eclipse Epsilon ETL (Epsilon Transformation Language) model-to-model transformation examples. The examples originate from https://github.com/eclipse-epsilon/epsilon/tree/main/examples.

ETL is a declarative rule-based language for transforming source models into target models. Models use XMI format; metamodels use Ecore (EMF standard).

## Running Transformations

**Via Eclipse IDE:** Open a `.launch` file → Right-click → Run As → Epsilon ETL Transformation.

**Via ANT (standalone):**
```
ant -f launch.xml
```
ANT scripts handle metamodel registration, model loading, ETL execution, and trace export.

There is no traditional build system, package manager, or test framework. The project depends on Eclipse Modeling Framework (EMF) and Epsilon runtime (Java/JVM).

## Architecture

```
ETL/
├── OO2DB/           # Object-Oriented → Relational DB schema (complex, multi-rule)
├── RSS2ATOM/        # RSS XML → ATOM XML feed conversion (lazy rules, XML models)
├── Tree2Graph/      # Tree hierarchy → Graph with nodes/edges (simple, single rule)
├── flowchart2html/  # Flowchart → HTML (7 variants demonstrating advanced patterns)
│   └── scripts/     # base/ equivalent/ greedy/ inheritance/ lazy/ multiple_targets/ primary/
└── ETL scripts/     # Standalone ETL files

resources/           # Shared copies of metamodels, models, and transformations
```

Each transformation project contains:
- `.etl` file — transformation rules
- `.ecore` files — metamodels defining source/target structure
- `.model` files — XMI instance data (source input and target output)
- `.launch` file — Eclipse run configuration
- `launch.xml` (some projects) — ANT build script

## ETL Language Conventions

**Rule naming:** `SourceType2TargetType` (e.g., `Class2Table`, `Tree2Node`)

**Metamodel references:** `MetamodelName!ClassName` (e.g., `OO!Class`, `DB!Table`)

**Key rule annotations:**
- `@lazy` — only invoked on-demand via `.equivalent()`
- `@greedy` — applies to all matching elements broadly
- `@primary` — disambiguates when multiple rules match the same source type
- `guard` — conditional rule execution
- `extends` — rule inheritance/specialization

**Built-in operations:** `::=` (equivalent shorthand), `.equivalent()`, `.allInstances()`, `.isDefined()`

**Structure:** Pre-block (setup) → rules execute → post-block (cleanup/tracing). Helper operations are defined at the bottom of ETL files.

## The Four Example Transformations

- **OO2DB** — Most complex. Transforms classes/attributes/references into tables/columns/foreign keys. Demonstrates guards, pre/post blocks, type mapping, traceability, and multi-valued attribute handling.
- **Tree2Graph** — Simplest. Single rule converts tree nodes to graph nodes with conditional edge creation.
- **RSS2ATOM** — Feed format conversion using `@lazy` rules and XML models (not EMF).
- **flowchart2html** — Seven variant implementations of the same transformation, each demonstrating a different ETL feature (`@lazy`, `@greedy`, `@primary`, `extends`, `::=` operator, multiple targets).
