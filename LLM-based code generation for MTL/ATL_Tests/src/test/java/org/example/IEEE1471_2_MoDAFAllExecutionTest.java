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
 * Integration test for the IEEE1471→MoDAF transformation. The test
 * loads a concrete IEEE1471 model and verifies that the resulting
 * MoDAF model contains the expected elements.
 */
public class IEEE1471_2_MoDAFAllExecutionTest {

    private ResourceSet rs;
    private EPackage ieee1471Pkg;
    private EPackage modafPkg;

    @BeforeEach
    // Initialize a new resource set and load the IEEE1471 and MoDAF metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        ieee1471Pkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/IEEE1471ConceptualModel.ecore");
        modafPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/MoDAF-AV.ecore");
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

    // Load an Ecore metamodel from the given path and register it in the
    // package registry of the given resource set.  Returns the loaded EPackage.
    private EPackage loadAndRegisterEcore(ResourceSet rs, String ecorePath) {
        URI uri = URI.createFileURI(new File(ecorePath).getAbsolutePath());
        Resource res = rs.getResource(uri, true);
        EPackage pkg = (EPackage) res.getContents().get(0);
        rs.getPackageRegistry().put(pkg.getNsURI(), pkg);
        return pkg;
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
    public void testIEEE1471_2_MoDAF() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("IEEE1471_2_MoDAF_All.atl");
        // Use the provided IEEE1471 input model
        File input = new File("src/main/resources/models", "ieee1471_input.xmi");
        assertTrue(input.exists(), "ieee1471_input.xmi not found: " + input.getAbsolutePath());

        // Register the IEEE1471 metamodel in the global package registry.
        // The ATL injector will use this to resolve the namespace when loading the input XMI.
        EPackage.Registry.INSTANCE.put(ieee1471Pkg.getNsURI(), ieee1471Pkg);
        // Also register the output metamodel for loading the output XMI
        EPackage.Registry.INSTANCE.put(modafPkg.getNsURI(), modafPkg);

        // Execute the transformation
        Resource outRes = executeAtl(asm, "IEEE1471ConceptualModel.ecore", "MoDAF-AV.ecore", "IEEE1471", "MoDAF", input);
        
        // Validate the resulting MoDAF model.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");
        
        EClass modafModelCls = (EClass) modafPkg.getEClassifier("MoDAFModel");
        EClass enterpriseCls = (EClass) modafPkg.getEClassifier("Enterprise");
        EClass environmentCls = (EClass) modafPkg.getEClassifier("Environment");
        
        int modafModelCount = 0;
        int enterpriseCount = 0;
        int environmentCount = 0;
        EObject modafModel = null;
        
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (modafModelCls.isInstance(obj)) {
                modafModelCount++;
                modafModel = obj;
            }
            if (enterpriseCls.isInstance(obj)) {
                enterpriseCount++;
            }
            if (environmentCls.isInstance(obj)) {
                environmentCount++;
            }
        }
        
        assertEquals(1, modafModelCount, "Expected one MoDAF MoDAFModel");
        assertEquals(1, enterpriseCount, "Expected one Enterprise");
        assertEquals(1, environmentCount, "Expected one Environment");
        assertNotNull(modafModel, "MoDAFModel is null");
        
        // Verify MoDAFModel name
        String modafModelName = (String) modafModel.eGet(modafModelCls.getEStructuralFeature("name"));
        assertEquals("TestModel", modafModelName, "MoDAFModel name should match IEEE1471Model name");
    }
}

