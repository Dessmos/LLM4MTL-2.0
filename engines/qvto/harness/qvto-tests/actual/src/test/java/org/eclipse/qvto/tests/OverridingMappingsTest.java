package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests OverridingMappings.qvto: polymorphic dispatch of overriding mappings.
 * Multiple makeClass() mappings defined for different levels of the type hierarchy.
 * Since input classifiers are EClass instances, EClass::makeClass() is dispatched.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with EClasses "CLASS:A", "CLASS:B", "CLASS:C"
 */
class OverridingMappingsTest extends QvtoTestBase {

    private static final String QVTO = "OverridingMappings.qvto";

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
    void outputReflectsPolymorphicDispatch() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        assertEquals(3, outPkg.getEClassifiers().size());
        // EClass::makeClass() is the most specific match for EClass inputs
        assertHasClass(outPkg, "CLASS:A");
        assertHasClass(outPkg, "CLASS:B");
        assertHasClass(outPkg, "CLASS:C");
    }
}
