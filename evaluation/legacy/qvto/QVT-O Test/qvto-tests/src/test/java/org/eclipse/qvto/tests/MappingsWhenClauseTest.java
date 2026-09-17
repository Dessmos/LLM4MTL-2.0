package org.eclipse.qvto.tests;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests MappingsWhenClause.qvto: when guard on mappings.
 * Only classifiers with name = 'A' pass the when-clause.
 * Input: EPackage "root" with EClasses A, B, C
 * Expected output: EPackage "root" with only EClass "mappedA"
 */
class MappingsWhenClauseTest extends QvtoTestBase {

    private static final String QVTO = "MappingsWhenClause.qvto";

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
    void outputFiltersWithWhenClause() {
        BasicModelExtent input = loadInputModel("models/in.ecore");
        BasicModelExtent output = executeTransformation(QVTO, input);
        EPackage outPkg = getSingleRootPackage(output);

        assertEquals("root", outPkg.getName());
        // Only A passes the when clause {self.name = 'A'}
        assertEquals(1, outPkg.getEClassifiers().size());
        assertHasClass(outPkg, "mappedA");
        assertNull(findClassifier(outPkg, "mappedB"), "B should be filtered by when clause");
        assertNull(findClassifier(outPkg, "mappedC"), "C should be filtered by when clause");
    }
}
