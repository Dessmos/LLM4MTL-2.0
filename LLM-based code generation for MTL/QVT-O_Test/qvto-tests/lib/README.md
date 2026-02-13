# Required Eclipse JARs

Place the following JAR files in this directory, then run `install-deps.cmd` from the project root.

## How to obtain

1. Download from an Eclipse IDE installation (`plugins/` directory), or
2. Download from Eclipse update site / p2 repository

## Required JARs (rename to these exact filenames)

| Filename | Source Bundle |
|----------|-------------|
| `org.eclipse.m2m.qvt.oml.jar` | org.eclipse.m2m.qvt.oml_3.11.0.*.jar |
| `org.eclipse.m2m.qvt.oml.common.jar` | org.eclipse.m2m.qvt.oml.common_3.11.0.*.jar |
| `org.eclipse.m2m.qvt.oml.cst.parser.jar` | org.eclipse.m2m.qvt.oml.cst.parser_3.11.0.*.jar |
| `org.eclipse.m2m.qvt.oml.emf.util.jar` | org.eclipse.m2m.qvt.oml.emf.util_3.11.0.*.jar |
| `org.eclipse.m2m.qvt.oml.ecore.imperativeocl.jar` | org.eclipse.m2m.qvt.oml.ecore.imperativeocl_3.11.0.*.jar |
| `org.eclipse.m2m.qvt.oml.runtime.jar` | org.eclipse.m2m.qvt.oml.runtime_3.11.0.*.jar |
| `org.eclipse.ocl.jar` | org.eclipse.ocl_3.18.0.*.jar |
| `org.eclipse.ocl.ecore.jar` | org.eclipse.ocl.ecore_3.18.0.*.jar |
| `org.eclipse.ocl.common.jar` | org.eclipse.ocl.common_1.9.0.*.jar |
| `lpg.runtime.java.jar` | lpg.runtime.java_2.0.17.*.jar |
| `org.eclipse.equinox.common.jar` | org.eclipse.equinox.common_3.19.0.*.jar |

Strip the version qualifier from the filename (e.g., rename `org.eclipse.m2m.qvt.oml_3.11.0.v20230101.jar` to `org.eclipse.m2m.qvt.oml.jar`).
