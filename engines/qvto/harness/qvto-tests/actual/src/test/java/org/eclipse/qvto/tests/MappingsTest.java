package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests Mappings.qvto: basic EPackage and EClassifier mapping.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EClasses "mappedA", "mappedB", "mappedC"
 */
class MappingsTest extends QvtoTestBase {

    private static final String QVTO = "Mappings.qvto";

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
    void outputContainsMappedClassifiers() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());
        assertHasClass(outPkg, "mappedA");
        assertHasClass(outPkg, "mappedB");
        assertHasClass(outPkg, "mappedC");
    }
}
