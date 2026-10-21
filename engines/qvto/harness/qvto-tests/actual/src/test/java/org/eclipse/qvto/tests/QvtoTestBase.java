package org.eclipse.qvto.tests;

import java.net.URL;
import java.util.List;

import org.eclipse.emf.common.util.BasicDiagnostic;
import org.eclipse.emf.common.util.Diagnostic;
import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EClass;
import org.eclipse.emf.ecore.EClassifier;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.EcorePackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.EcoreResourceFactoryImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.eclipse.m2m.qvt.oml.BasicModelExtent;
import org.eclipse.m2m.qvt.oml.ExecutionContextImpl;
import org.eclipse.m2m.qvt.oml.ExecutionDiagnostic;
import org.eclipse.m2m.qvt.oml.TransformationExecutor;
import org.junit.jupiter.api.BeforeAll;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Base class for QVT-O transformation tests.
 * Provides EMF registration, model loading, and transformation execution helpers.
 */
public abstract class QvtoTestBase {

    @BeforeAll
    static void registerEMF() {
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
                .put("ecore", new EcoreResourceFactoryImpl());
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
                .put("xmi", new XMIResourceFactoryImpl());
        EPackage.Registry.INSTANCE.put(EcorePackage.eNS_URI, EcorePackage.eINSTANCE);
    }

    /**
     * Loads an Ecore model from the classpath.
     */
    protected static BasicModelExtent loadInputModel(String resourcePath) {
        ResourceSet rs = new ResourceSetImpl();
        URL url = QvtoTestBase.class.getClassLoader().getResource(resourcePath);
        assertNotNull(url, "Resource not found: " + resourcePath);
        URI uri = URI.createURI(url.toString());
        Resource resource = rs.getResource(uri, true);
        assertNotNull(resource, "Failed to load resource: " + resourcePath);
        return new BasicModelExtent(resource.getContents());
    }

    /**
     * Returns the URI for a .qvto transformation on the classpath.
     */
    protected static URI getTransformationURI(String qvtoFile) {
        URL url = QvtoTestBase.class.getClassLoader().getResource("transformations/" + qvtoFile);
        assertNotNull(url, "Transformation not found: " + qvtoFile);
        return URI.createURI(url.toString());
    }

    /**
     * Executes a QVT-O transformation with 1 input and 1 output extent.
     * Asserts that execution succeeds (Diagnostic.OK).
     */
    protected static BasicModelExtent executeTransformation(String qvtoFile, BasicModelExtent input) {
        URI txURI = getTransformationURI(qvtoFile);
        TransformationExecutor executor = new TransformationExecutor(txURI);
        BasicModelExtent output = new BasicModelExtent();
        ExecutionContextImpl context = new ExecutionContextImpl();
        ExecutionDiagnostic diagnostic = executor.execute(context, input, output);
        assertEquals(Diagnostic.OK, diagnostic.getSeverity(),
                "Transformation failed: " + diagnostic.getMessage());
        return output;
    }

    /**
     * Executes a QVT-O transformation with 1 input and 2 output extents.
     * Asserts that execution succeeds (Diagnostic.OK).
     */
    protected static BasicModelExtent[] executeTransformation2Outputs(
            String qvtoFile, BasicModelExtent input) {
        URI txURI = getTransformationURI(qvtoFile);
        TransformationExecutor executor = new TransformationExecutor(txURI);
        BasicModelExtent output1 = new BasicModelExtent();
        BasicModelExtent output2 = new BasicModelExtent();
        ExecutionContextImpl context = new ExecutionContextImpl();
        ExecutionDiagnostic diagnostic = executor.execute(context, input, output1, output2);
        assertEquals(Diagnostic.OK, diagnostic.getSeverity(),
                "Transformation failed: " + diagnostic.getMessage());
        return new BasicModelExtent[]{output1, output2};
    }

    /**
     * Extracts the single root EPackage from a model extent.
     */
    protected static EPackage getSingleRootPackage(BasicModelExtent extent) {
        List<EObject> contents = extent.getContents();
        assertFalse(contents.isEmpty(), "Extent has no contents");
        assertTrue(contents.get(0) instanceof EPackage,
                "Root element is not EPackage, got: " + contents.get(0).eClass().getName());
        return (EPackage) contents.get(0);
    }

    /**
     * Finds a classifier by name in a package.
     */
    protected static EClassifier findClassifier(EPackage pkg, String name) {
        return pkg.getEClassifiers().stream()
                .filter(c -> name.equals(c.getName()))
                .findFirst()
                .orElse(null);
    }

    /**
     * Asserts that a classifier with the given name exists and is an EClass.
     */
    protected static EClass assertHasClass(EPackage pkg, String name) {
        EClassifier classifier = findClassifier(pkg, name);
        assertNotNull(classifier, "Expected EClass '" + name + "' not found in package '" + pkg.getName() + "'");
        assertTrue(classifier instanceof EClass,
                "Classifier '" + name + "' is not an EClass, got: " + classifier.eClass().getName());
        return (EClass) classifier;
    }
}
