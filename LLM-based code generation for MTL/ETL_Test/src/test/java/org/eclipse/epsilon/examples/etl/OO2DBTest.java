package org.eclipse.epsilon.examples.etl;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

public class OO2DBTest extends EtlTestBase {

    @BeforeEach
    public void setUp() throws Exception {
        registerMetamodel("metamodels/OO.ecore");
        registerMetamodel("metamodels/DB.ecore");
        registerMetamodel("metamodels/TM.ecore");
        registerMetamodel("metamodels/SimpleTrace.ecore");
    }

    @Test
    public void testOO2DB() throws Exception {
        // Load source models
        EmfModel ooModel = createEmfModel("OO", "models/OOInstance.model",
            "OO", true, false);
        EmfModel tmModel = createEmfModel("OO2DB", "models/OO2DB.model",
            "TM", true, false);

        // Create target models
        File dbFile = File.createTempFile("db_output", ".model");
        dbFile.deleteOnExit();
        EmfModel dbModel = createEmfModelFromFile("DB", dbFile.getAbsolutePath(),
            "DB", false, false);

        File traceFile = File.createTempFile("trace_output", ".model");
        traceFile.deleteOnExit();
        EmfModel traceModel = createEmfModelFromFile("Trace", traceFile.getAbsolutePath(),
            "SimpleTrace", false, false);

        runEtl("transformations/OO2DB.etl", ooModel, tmModel, dbModel, traceModel);

        // Verify tables created
        Collection<?> tables = dbModel.getAllOfType("Table");
        Set<String> tableNames = tables.stream()
            .map(t -> {
                EObject e = (EObject) t;
                return (String) e.eGet(e.eClass().getEStructuralFeature("name"));
            })
            .collect(Collectors.toSet());

        assertEquals(7, tables.size(), "Should have 7 tables");
        assertTrue(tableNames.contains("School"), "Should have School table");
        assertTrue(tableNames.contains("Student"), "Should have Student table");
        assertTrue(tableNames.contains("Person"), "Should have Person table");
        assertTrue(tableNames.contains("Employee"), "Should have Employee table");
        assertTrue(tableNames.contains("Teacher"), "Should have Teacher table");
        assertTrue(tableNames.contains("Class"), "Should have Class table");
        assertTrue(tableNames.contains("School_PostCodesAcceptedValues"),
            "Should have School_PostCodesAcceptedValues table");

        // Verify foreign keys
        Collection<?> foreignKeys = dbModel.getAllOfType("ForeignKey");
        Set<String> fkNames = foreignKeys.stream()
            .map(fk -> {
                EObject e = (EObject) fk;
                return (String) e.eGet(e.eClass().getEStructuralFeature("name"));
            })
            .filter(name -> name != null)
            .collect(Collectors.toSet());

        assertTrue(fkNames.contains("StudentExtendsPerson"),
            "Should have StudentExtendsPerson FK");
        assertTrue(fkNames.contains("EmployeeExtendsPerson"),
            "Should have EmployeeExtendsPerson FK");
        assertTrue(fkNames.contains("TeacherExtendsEmployee"),
            "Should have TeacherExtendsEmployee FK");

        // Verify trace model has links
        Collection<?> traceLinks = traceModel.getAllOfType("TraceLink");
        assertFalse(traceLinks.isEmpty(), "Trace model should have TraceLink instances");
    }
}
