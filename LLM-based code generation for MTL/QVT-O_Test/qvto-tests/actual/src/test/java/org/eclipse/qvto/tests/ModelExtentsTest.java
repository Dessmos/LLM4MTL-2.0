package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests ModelExtents.qvto: multiple output model extents.
 * Transformation has 1 input (m) and 2 outputs (x, y).
 * Creates EPackage "a" in extent x, EPackage "b" in extent y.
 * Input model is not used by main().
 */
class ModelExtentsTest extends QvtoTestBase {

    private static final String QVTO = "ModelExtents.qvto";

    @Test
    void transformationLoadsSuccessfully() {
        assertNotNull(getTransformationURI(QVTO));
    }

    @Test
    void executesSuccessfully() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent[] outputs = executeTransformation2Outputs(QVTO, input);
        assertNotNull(outputs);
        assertEquals(2, outputs.length);
    }

    @Test
    void outputExtentsContainCorrectPackages() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent[] outputs = executeTransformation2Outputs(QVTO, input);

        // Extent x should contain EPackage "a"
        BasicModelExtent extentX = outputs[0];
        List<EObject> xContents = extentX.getContents();
        assertFalse(xContents.isEmpty(), "Extent x should not be empty");
        assertTrue(xContents.get(0) instanceof EPackage, "Extent x root should be EPackage");
        assertEquals("a", ((EPackage) xContents.get(0)).getName());

        // Extent y should contain EPackage "b"
        BasicModelExtent extentY = outputs[1];
        List<EObject> yContents = extentY.getContents();
        assertFalse(yContents.isEmpty(), "Extent y should not be empty");
        assertTrue(yContents.get(0) instanceof EPackage, "Extent y root should be EPackage");
        assertEquals("b", ((EPackage) yContents.get(0)).getName());
    }
}
