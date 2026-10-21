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
 * Integration test for the CPL→SPL transformation. The test
 * loads a concrete CPL model and verifies that the resulting
 * SPL model contains the expected elements.
 */
public class CPL2SPLAllExecutionTest {

    private ResourceSet rs;
    private EPackage cplPkg;
    private EPackage splPkg;

    @BeforeEach
    // Initialize a new resource set and load the CPL and SPL metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        cplPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/CPL.ecore");
        splPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/SPL.ecore");
    }
    
    @BeforeAll
    // Register resource factories for XMI and Ecore files once before all tests.
    public static void registerResourceFactories() {
        // Register the factories for XMI and Ecore files
        Resource.Factory.Registry reg = Resource.Factory.Registry.INSTANCE;
        Map<String, Object> extensionToFactoryMap = reg.getExtensionToFactoryMap();
        extensionToFactoryMap.put("xmi", new XMIResourceFactoryImpl());
        extensionToFactoryMap.put("ecore", new EcoreResourceFactoryImpl());
    }

    // Compile the given ATL file to a temporary ASM file and return it.
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

    // Load an Ecore metamodel from the given path and register all packages
    // in the package registry of the given resource set.  Returns the EPackage
    // whose name matches the file name (handles multi-package .ecore files).
    private EPackage loadAndRegisterEcore(ResourceSet rs, String ecorePath) {
        URI uri = URI.createFileURI(new File(ecorePath).getAbsolutePath());
        Resource res = rs.getResource(uri, true);
        EPackage mainPkg = null;
        String expectedName = new File(ecorePath).getName().replace(".ecore", "");
        for (org.eclipse.emf.ecore.EObject obj : res.getContents()) {
            if (obj instanceof EPackage) {
                EPackage pkg = (EPackage) obj;
                if (pkg.getNsURI() != null) {
                    rs.getPackageRegistry().put(pkg.getNsURI(), pkg);
                }
                if (pkg.getName().equals(expectedName)) {
                    mainPkg = pkg;
                }
            }
        }
        if (mainPkg == null) {
            mainPkg = (EPackage) res.getContents().get(0);
        }
        return mainPkg;
    }

    // Execute the given ATL transformation and return the output resource.
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
        // Extract to temporary file
        File outFile = Files.createTempFile("atlOut", ".xmi").toFile();
        outFile.deleteOnExit();
        extractor.extract(outModel, URI.createFileURI(outFile.getAbsolutePath()).toString());
        // Load output resource into the test's resource set
        return rs.getResource(URI.createFileURI(outFile.getAbsolutePath()), true);
    }

    @Test
    public void testCPL2SPL() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("CPL2SPL_All.atl");
        // Use the provided CPL input model
        File input = new File("src/main/resources/models", "cpl_input.xmi");
        assertTrue(input.exists(), "cpl_input.xmi not found: " + input.getAbsolutePath());

        // Register the CPL metamodel in the global package registry.
        // The ATL injector will use this to resolve the namespace when loading the input XMI.
        EPackage.Registry.INSTANCE.put(cplPkg.getNsURI(), cplPkg);
        
        // Execute the transformation
        Resource outRes = executeAtl(asm, "CPL.ecore", "SPL.ecore", "CPL", "SPL", input);
        
        // Validate the resulting SPL model.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");
        
        EClass programCls = (EClass) splPkg.getEClassifier("Program");
        EClass serviceCls = (EClass) splPkg.getEClassifier("Service");
        
        int programCount = 0;
        int serviceCount = 0;
        EObject program = null;
        
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (programCls.isInstance(obj)) {
                programCount++;
                program = obj;
            }
            if (serviceCls.isInstance(obj)) {
                serviceCount++;
            }
        }
        
        assertEquals(1, programCount, "Expected one SPL Program");
        assertEquals(1, serviceCount, "Expected one SPL Service");
        assertNotNull(program, "Program is null");
        
        // Verify Program contains service (single-valued reference)
        EObject service = (EObject) program.eGet(programCls.getEStructuralFeature("service"));
        assertNotNull(service, "Program should contain a service");
        assertTrue(serviceCls.isInstance(service), "Program's service should be a Service");
    }
}

