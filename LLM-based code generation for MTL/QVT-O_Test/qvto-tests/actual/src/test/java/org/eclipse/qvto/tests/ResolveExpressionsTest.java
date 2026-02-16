package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests ResolveExpressions.qvto: resolve and resolveoneIn expressions.
 * After mapping, resolves the first input classifier's mapped EClass,
 * takes substring(1,6) of its name ("mapped") and prepends to the output package name.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "mappedroot" with EClasses "mappedA", "mappedB", "mappedC"
 */
class ResolveExpressionsTest extends QvtoTestBase {

    private static final String QVTO = "ResolveExpressions.qvto";

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
    void outputReflectsResolveExpression() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        // Package name is modified by resolve: "mapped" + "root" = "mappedroot"
        assertEquals("mappedroot", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());
        assertHasClass(outPkg, "mappedA");
        assertHasClass(outPkg, "mappedB");
        assertHasClass(outPkg, "mappedC");
    }
}
