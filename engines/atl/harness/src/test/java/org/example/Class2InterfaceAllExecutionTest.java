package org.example;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.io.FileReader;
import java.io.Reader;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

import org.eclipse.emf.common.util.EList;
import org.eclipse.emf.common.util.TreeIterator;
import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EClass;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.EcoreResourceFactoryImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.eclipse.m2m.atl.core.IExtractor;
import org.eclipse.m2m.atl.core.IInjector;
import org.eclipse.m2m.atl.core.IModel;
import org.eclipse.m2m.atl.core.IReferenceModel;
import org.eclipse.m2m.atl.core.ModelFactory;
import org.eclipse.m2m.atl.core.emf.EMFExtractor;
import org.eclipse.m2m.atl.core.emf.EMFInjector;
import org.eclipse.m2m.atl.core.emf.EMFModelFactory;
import org.eclipse.m2m.atl.engine.compiler.atl2006.Atl2006Compiler;
import org.eclipse.m2m.atl.engine.emfvm.launch.EMFVMLauncher;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Integration test for the Class->Interface transformation.  The test
 * loads a Class model with one class "Calculator" containing two methods,
 * runs the ATL module and verifies that the resulting Interface model
 * contains the expected interface with methods and parameters.
 */
public class Class2InterfaceAllExecutionTest {

    private ResourceSet rs;
    private EPackage classPkg;
    private EPackage interfacePkg;

    @BeforeEach
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        classPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Class.ecore");
        interfacePkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Interface.ecore");
    }

    @BeforeAll
    public static void registerResourceFactories() {
        Resource.Factory.Registry reg = Resource.Factory.Registry.INSTANCE;
        Map<String, Object> extensionToFactoryMap = reg.getExtensionToFactoryMap();
        extensionToFactoryMap.put("xmi", new XMIResourceFactoryImpl());
        extensionToFactoryMap.put("ecore", new EcoreResourceFactoryImpl());
    }

    private File compileAtl(String atlFileName) throws Exception {
        File atlFile = new File("src/main/atl", atlFileName);
        assertTrue(atlFile.exists(), "ATL file not found: " + atlFile.getAbsolutePath());
        File asmFile = Files.createTempFile("atltest", ".asm").toFile();
        asmFile.deleteOnExit();
        try (Reader reader = new FileReader(atlFile)) {
            new Atl2006Compiler().compile(reader, asmFile.getAbsolutePath());
        }
        assertTrue(asmFile.length() > 0, "Compiled ASM file is empty for " + atlFileName);
        return asmFile;
    }

    private EPackage loadAndRegisterEcore(ResourceSet rs, String ecorePath) {
        URI uri = URI.createFileURI(new File(ecorePath).getAbsolutePath());
        Resource res = rs.getResource(uri, true);
        EPackage pkg = (EPackage) res.getContents().get(0);
        rs.getPackageRegistry().put(pkg.getNsURI(), pkg);
        return pkg;
    }

    private Resource executeAtl(File asmFile, String inEcore, String outEcore, String inAlias, String outAlias, File inputXmi) throws Exception {
        ModelFactory factory = new EMFModelFactory();
        IInjector injector = new EMFInjector();
        IExtractor extractor = new EMFExtractor();
        IReferenceModel inMM = factory.newReferenceModel();
        injector.inject(inMM, URI.createFileURI(new File("src/main/resources/metamodels", inEcore).getAbsolutePath()).toString());
        IReferenceModel outMM = factory.newReferenceModel();
        injector.inject(outMM, URI.createFileURI(new File("src/main/resources/metamodels", outEcore).getAbsolutePath()).toString());
        IModel inModel = factory.newModel(inMM);
        injector.inject(inModel, URI.createFileURI(inputXmi.getAbsolutePath()).toString());
        IModel outModel = factory.newModel(outMM);
        EMFVMLauncher launcher = new EMFVMLauncher();
        launcher.initialize(null);
        launcher.addInModel(inModel, "IN", inAlias);
        launcher.addOutModel(outModel, "OUT", outAlias);
        Map<String,Object> options = new HashMap<>();
        try (java.io.InputStream is = new java.io.FileInputStream(asmFile)) {
            launcher.launch("run", null, options, is);
        }
        File outFile = Files.createTempFile("atlOut", ".xmi").toFile();
        outFile.deleteOnExit();
        extractor.extract(outModel, URI.createFileURI(outFile.getAbsolutePath()).toString());
        return rs.getResource(URI.createFileURI(outFile.getAbsolutePath()), true);
    }

    @Test
    public void testClass2Interface() throws Exception {
        File asm = compileAtl("Class2Interface_All.atl");
        File input = new File("src/main/resources/models", "class_input.xmi");
        assertTrue(input.exists(), "class_input.xmi not found: " + input.getAbsolutePath());

        EPackage.Registry.INSTANCE.put(classPkg.getNsURI(), classPkg);

        Resource outRes = executeAtl(asm, "Class.ecore", "Interface.ecore", "Class", "Interface", input);

        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass interfaceCls = (EClass) interfacePkg.getEClassifier("Interface");
        EClass methodCls = (EClass) interfacePkg.getEClassifier("Method");
        EClass paramCls = (EClass) interfacePkg.getEClassifier("Parameter");

        int interfaceCount = 0;
        int methodCount = 0;
        int paramCount = 0;
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (interfaceCls.isInstance(obj)) interfaceCount++;
            if (methodCls.isInstance(obj)) methodCount++;
            if (paramCls.isInstance(obj)) paramCount++;
        }
        assertEquals(1, interfaceCount, "Expected one Interface");
        assertEquals(2, methodCount, "Expected two Methods");
        assertEquals(4, paramCount, "Expected four Parameters");

        // Find the Interface and check its name
        EObject iface = null;
        for (EObject obj : outRes.getContents()) {
            if (interfaceCls.isInstance(obj)) {
                iface = obj;
                break;
            }
        }
        assertNotNull(iface, "Interface object not found");
        String name = (String) iface.eGet(interfaceCls.getEStructuralFeature("name"));
        assertEquals("Calculator", name, "Interface name should be Calculator");

        // Check methods
        @SuppressWarnings("unchecked")
        EList<EObject> methods = (EList<EObject>) iface.eGet(interfaceCls.getEStructuralFeature("methods"));
        assertEquals(2, methods.size(), "Interface should have two methods");
        boolean foundAdd = false;
        boolean foundSubtract = false;
        for (EObject m : methods) {
            String mName = (String) m.eGet(methodCls.getEStructuralFeature("name"));
            if ("add".equals(mName)) foundAdd = true;
            if ("subtract".equals(mName)) foundSubtract = true;
            // Each method should have 2 parameters
            @SuppressWarnings("unchecked")
            EList<EObject> params = (EList<EObject>) m.eGet(methodCls.getEStructuralFeature("parameters"));
            assertEquals(2, params.size(), "Method " + mName + " should have two parameters");
        }
        assertTrue(foundAdd, "Method 'add' missing");
        assertTrue(foundSubtract, "Method 'subtract' missing");
    }
}
