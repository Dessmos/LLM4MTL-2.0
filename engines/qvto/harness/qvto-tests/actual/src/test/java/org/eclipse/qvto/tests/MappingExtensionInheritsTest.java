package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests MappingExtensionInherits.qvto: mapping inheritance.
 * Abstract mapping appends '1', concrete mapping appends '2'.
 * With inherits, abstract body runs first, then concrete body.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EClasses "A12", "B12", "C12"
 */
class MappingExtensionInheritsTest extends QvtoTestBase {

    private static final String QVTO = "MappingExtensionInherits.qvto";

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
    void outputReflectsInheritance() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());
        // Abstract sets name = self.name+'1', then concrete sets name = name+'2'
        assertHasClass(outPkg, "A12");
        assertHasClass(outPkg, "B12");
        assertHasClass(outPkg, "C12");
    }
}
