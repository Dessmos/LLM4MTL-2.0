package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EClass;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests Constructors.qvto: custom constructor with parameters.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with 1 EClass "AClass" that has 1 EOperation
 */
class ConstructorsTest extends QvtoTestBase {

    private static final String QVTO = "Constructors.qvto";

    @Test
    void transformationLoadsSuccessfully() {
        assertNotNull(getTransformationURI(QVTO));
    }

    @Test
    void executesSuccessfully() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        assertNotNull(output);
        assertFalse(output.getContents().isEmpty());
    }

    @Test
    void outputContainsConstructedClass() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(1, outPkg.getEClassifiers().size());

        EClass aClass = assertHasClass(outPkg, "AClass");
        assertEquals(1, aClass.getEOperations().size(),
                "AClass should have exactly 1 EOperation");
    }
}
