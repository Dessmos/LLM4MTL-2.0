package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests MappingExtensionMerges.qvto: mapping merging.
 * Concrete mapping sets name = self.name+'2', then merged abstract appends '1'.
 * With merges, concrete body runs first, then merged body.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EClasses "A21", "B21", "C21"
 */
class MappingExtensionMergesTest extends QvtoTestBase {

    private static final String QVTO = "MappingExtensionMerges.qvto";

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
    void outputReflectsMerging() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());
        // Concrete sets name = self.name+'2', then merged sets name = name+'1'
        assertHasClass(outPkg, "A21");
        assertHasClass(outPkg, "B21");
        assertHasClass(outPkg, "C21");
    }
}
