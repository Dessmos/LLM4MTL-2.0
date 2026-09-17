package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests MappingExtensionDisjuncts.qvto: disjunct mapping dispatch.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EClasses "AA" and "BB" (C is filtered out
 * because it matches neither makeAClass nor makeBClass when-clauses)
 */
class MappingExtensionDisjunctsTest extends QvtoTestBase {

    private static final String QVTO = "MappingExtensionDisjuncts.qvto";

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
    void outputContainsDisjunctResults() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        // Only A and B match; C is filtered by disjuncts
        assertEquals(2, outPkg.getEClassifiers().size());
        assertHasClass(outPkg, "AA");
        assertHasClass(outPkg, "BB");
        assertNull(findClassifier(outPkg, "CC"),
                "C should not produce output (no matching disjunct)");
    }
}
