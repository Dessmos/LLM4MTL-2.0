package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EClassifier;
import org.eclipse.emf.ecore.EDataType;
import org.eclipse.emf.ecore.EClass;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests MappingBody.qvto: init block with polymorphic result type.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EDataType "mappedA", EClass "mappedB", EClass "mappedC"
 */
class MappingBodyTest extends QvtoTestBase {

    private static final String QVTO = "MappingBody.qvto";

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
    void outputContainsPolymorphicResults() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());

        // A maps to EDataType (init block condition: name = 'A')
        EClassifier mappedA = findClassifier(outPkg, "mappedA");
        assertNotNull(mappedA, "Expected 'mappedA' classifier");
        assertTrue(mappedA instanceof EDataType,
                "mappedA should be EDataType, got: " + mappedA.eClass().getName());

        // B and C map to EClass
        assertHasClass(outPkg, "mappedB");
        assertHasClass(outPkg, "mappedC");
    }
}
