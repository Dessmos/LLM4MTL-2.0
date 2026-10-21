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
 * Integration test for the PetriNet→Grafcet transformation. The test
 * loads a concrete PetriNet model with one PetriNet containing two Places
 * and one Transition. It runs the ATL module and verifies that the
 * resulting Grafcet model contains the expected elements.
 */
public class PetriNet2GrafcetAllExecutionTest {

    private ResourceSet rs;
    private EPackage petriNetPkg;
    private EPackage grafcetPkg;

    @BeforeEach
    // Initialize a new resource set and load the PetriNet and Grafcet metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        petriNetPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/PetriNet.ecore");
        grafcetPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Grafcet.ecore");
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
    // package registry of the given resource set. Returns the loaded EPackage.
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
    public void testPetriNet2Grafcet() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("PetriNet2Grafcet_All.atl");
        // Use the provided PetriNet input model
        File input = new File("src/main/resources/models", "petrinet_input.xmi");
        assertTrue(input.exists(), "petrinet_input.xmi not found: " + input.getAbsolutePath());

        // Register the PetriNet metamodel in the global package registry.
        // The ATL injector will use this to resolve the namespace when loading the input XMI.
        EPackage.Registry.INSTANCE.put(petriNetPkg.getNsURI(), petriNetPkg);
        
        // Execute the transformation
        Resource outRes = executeAtl(asm, "PetriNet.ecore", "Grafcet.ecore", "PetriNet", "Grafcet", input);
        
        // Validate the resulting Grafcet model.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");
        
        EClass grafcetCls = (EClass) grafcetPkg.getEClassifier("Grafcet");
        EClass stepCls = (EClass) grafcetPkg.getEClassifier("Step");
        EClass transitionCls = (EClass) grafcetPkg.getEClassifier("Transition");
        EClass connectionCls = (EClass) grafcetPkg.getEClassifier("Connection");
        
        int grafcetCount = 0;
        int stepCount = 0;
        int transitionCount = 0;
        int connectionCount = 0;
        EObject grafcet = null;
        
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (grafcetCls.isInstance(obj)) {
                grafcetCount++;
                grafcet = obj;
            }
            if (stepCls.isInstance(obj)) {
                stepCount++;
            }
            if (transitionCls.isInstance(obj)) {
                transitionCount++;
            }
            if (connectionCls.isInstance(obj)) {
                connectionCount++;
            }
        }
        
        assertEquals(1, grafcetCount, "Expected one Grafcet");
        assertEquals(2, stepCount, "Expected two Step objects (from two Places)");
        assertEquals(1, transitionCount, "Expected one Transition object");
        assertEquals(2, connectionCount, "Expected two Connection objects");
        assertNotNull(grafcet, "Grafcet is null");
        
        // Verify Grafcet name and structure
        EClass namedCls = (EClass) grafcetPkg.getEClassifier("NamedElement");
        String grafcetName = (String) grafcet.eGet(namedCls.getEStructuralFeature("name"));
        assertEquals("TestPetriNet", grafcetName, "Grafcet name should match PetriNet name");
        
        // Verify elements are contained in the Grafcet
        @SuppressWarnings("unchecked")
        EList<EObject> elements = (EList<EObject>) grafcet.eGet(grafcetCls.getEStructuralFeature("elements"));
        assertEquals(3, elements.size(), "Grafcet should contain 3 elements (2 Steps + 1 Transition)");
        
        // Verify connections are contained in the Grafcet
        @SuppressWarnings("unchecked")
        EList<EObject> connections = (EList<EObject>) grafcet.eGet(grafcetCls.getEStructuralFeature("connections"));
        assertEquals(2, connections.size(), "Grafcet should contain 2 connections");
    }
}

