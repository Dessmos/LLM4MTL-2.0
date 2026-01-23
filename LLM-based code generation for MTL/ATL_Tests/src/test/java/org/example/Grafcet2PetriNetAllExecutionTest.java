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
 * Integration test for the Grafcet→PetriNet transformation. The test
 * loads a concrete Grafcet model with one Grafcet containing two Steps
 * and one Transition. It runs the ATL module and verifies that the
 * resulting PetriNet model contains the expected elements.
 */
public class Grafcet2PetriNetAllExecutionTest {

    private ResourceSet rs;
    private EPackage grafcetPkg;
    private EPackage petriNetPkg;

    @BeforeEach
    // Initialize a new resource set and load the Grafcet and PetriNet metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        grafcetPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Grafcet.ecore");
        petriNetPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/PetriNet.ecore");
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
    // package registry of the given resource set. Returns the main EPackage (matching filename or first valid).
    private EPackage loadAndRegisterEcore(ResourceSet rs, String ecorePath) {
        URI uri = URI.createFileURI(new File(ecorePath).getAbsolutePath());
        Resource res = rs.getResource(uri, true);
        EPackage result = null;
        // Extract expected package name from filename (e.g., "PetriNet.ecore" -> "PetriNet")
        String expectedName = new File(ecorePath).getName().replace(".ecore", "");
        // Register all packages in the resource
        for (org.eclipse.emf.ecore.EObject obj : res.getContents()) {
            if (obj instanceof EPackage) {
                EPackage pkg = (EPackage) obj;
                if (pkg.getNsURI() != null) {
                    rs.getPackageRegistry().put(pkg.getNsURI(), pkg);
                    // Prefer package matching the filename
                    if (pkg.getName().equals(expectedName)) {
                        result = pkg;
                    } else if (result == null && !pkg.getName().equals("PrimitiveTypes")) {
                        result = pkg;
                    }
                }
            }
        }
        return result != null ? result : (EPackage) res.getContents().get(0);
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
    public void testGrafcet2PetriNet() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("Grafcet2PetriNet_All.atl");
        // Use the provided Grafcet input model
        File input = new File("src/main/resources/models", "grafcet_input.xmi");
        assertTrue(input.exists(), "grafcet_input.xmi not found: " + input.getAbsolutePath());

        // Register the Grafcet metamodel in the global package registry.
        // The ATL injector will use this to resolve the namespace when loading the input XMI.
        EPackage.Registry.INSTANCE.put(grafcetPkg.getNsURI(), grafcetPkg);
        // Also register the output metamodel for loading the output XMI
        EPackage.Registry.INSTANCE.put(petriNetPkg.getNsURI(), petriNetPkg);

        // Execute the transformation
        Resource outRes = executeAtl(asm, "Grafcet.ecore", "PetriNet.ecore", "Grafcet", "PetriNet", input);
        
        // Validate the resulting PetriNet model.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");
        
        EClass petriNetCls = (EClass) petriNetPkg.getEClassifier("PetriNet");
        EClass placeCls = (EClass) petriNetPkg.getEClassifier("Place");
        EClass transitionCls = (EClass) petriNetPkg.getEClassifier("Transition");
        EClass arcCls = (EClass) petriNetPkg.getEClassifier("Arc");
        
        int petriNetCount = 0;
        int placeCount = 0;
        int transitionCount = 0;
        int arcCount = 0;
        EObject petriNet = null;
        
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (petriNetCls.isInstance(obj)) {
                petriNetCount++;
                petriNet = obj;
            }
            if (placeCls.isInstance(obj)) {
                placeCount++;
            }
            if (transitionCls.isInstance(obj)) {
                transitionCount++;
            }
            if (arcCls.isInstance(obj)) {
                arcCount++;
            }
        }
        
        assertEquals(1, petriNetCount, "Expected one PetriNet");
        assertEquals(2, placeCount, "Expected two Place objects (from two Steps)");
        assertEquals(1, transitionCount, "Expected one Transition object");
        assertEquals(2, arcCount, "Expected two Arc objects");
        assertNotNull(petriNet, "PetriNet is null");
        
        // Verify PetriNet name and structure
        EClass namedCls = (EClass) petriNetPkg.getEClassifier("NamedElement");
        String petriNetName = (String) petriNet.eGet(namedCls.getEStructuralFeature("name"));
        assertEquals("TestGrafcet", petriNetName, "PetriNet name should match Grafcet name");
        
        // Verify elements are contained in the PetriNet
        @SuppressWarnings("unchecked")
        EList<EObject> elements = (EList<EObject>) petriNet.eGet(petriNetCls.getEStructuralFeature("elements"));
        assertEquals(3, elements.size(), "PetriNet should contain 3 elements (2 Places + 1 Transition)");
        
        // Verify arcs are contained in the PetriNet
        @SuppressWarnings("unchecked")
        EList<EObject> arcs = (EList<EObject>) petriNet.eGet(petriNetCls.getEStructuralFeature("arcs"));
        assertEquals(2, arcs.size(), "PetriNet should contain 2 arcs");
    }
}

