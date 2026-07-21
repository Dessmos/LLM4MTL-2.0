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
 * Integration test for the combined Network→Graph transformation.  The test
 * loads the concrete Network model with a single System containing two
 * components and one link connecting them.  It runs the ATL module and
 * verifies that the resulting Graph model contains exactly one Root, two
 * Entity objects with the correct names and a single Link referencing those
 * entities.
 */
public class NetworkToGraphAllExecutionTest {

    private ResourceSet rs;
    private EPackage networkPkg;
    private EPackage graphPkg;


    @BeforeEach
    // Initialize a new resource set and load the Amalthea and Ascet metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        networkPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/network.ecore");
        graphPkg    = loadAndRegisterEcore(rs, "src/main/resources/metamodels/graph.ecore");
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
    public void testNetworkToGraph() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("NetworkToGraph_All.atl");
        // Use the provided network input XMI rather than constructing the model in code.
        File input = new File("src/main/resources/models", "network_input.xmi");
        assertTrue(input.exists(), "network_input.xmi not found: " + input.getAbsolutePath());

        // Register the network metamodel in the global package registry so the
        // injector can resolve the namespace used in the XMI document.
        EPackage.Registry.INSTANCE.put(networkPkg.getNsURI(), networkPkg);

        // Execute the transformation
        Resource outRes = executeAtl(asm, "network.ecore", "graph.ecore", "Network", "Graph", input);
        
        // Validate the resulting Graph model.  There should be one Root, two
        // Entity instances and one Link instance based on the sample input.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass rootCls = (EClass) graphPkg.getEClassifier("Root");
        EClass entityCls = (EClass) graphPkg.getEClassifier("Entity");
        EClass linkCls = (EClass) graphPkg.getEClassifier("Link");
        int rootCount = 0;
        int entityCount = 0;
        int linkCount = 0;
        
        // The output model has a flat structure, so we iterate over the direct contents.
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (rootCls.isInstance(obj)) rootCount++;
            if (entityCls.isInstance(obj)) entityCount++;
            if (linkCls.isInstance(obj)) linkCount++;
        }
        assertEquals(1, rootCount, "Expected one Graph Root");
        assertEquals(2, entityCount, "Expected two Graph Entity objects");
        assertEquals(1, linkCount, "Expected one Graph Link object");
        // Check that entities are children of the root and have correct names
        EObject root = null;
        for (EObject obj : outRes.getContents()) {
            if (rootCls.isInstance(obj)) {
                root = obj;
                break;
            }
        }
        assertNotNull(root, "Root object not found");
        @SuppressWarnings("unchecked")
        EList<EObject> entities = (EList<EObject>) root.eGet(rootCls.getEStructuralFeature("entities"));
        assertEquals(2, entities.size(), "Root should reference two entities");
        boolean foundDevice = false;
        boolean foundServer = false;
        for (EObject ent : entities) {
            String name = (String) ent.eGet(entityCls.getEStructuralFeature("name"));
            if ("DeviceA".equals(name)) foundDevice = true;
            if ("ServerB".equals(name)) foundServer = true;
        }
        assertTrue(foundDevice, "Entity 'DeviceA' missing");
        assertTrue(foundServer, "Entity 'ServerB' missing");
        // Verify that the link references both entities
        EObject graphLink = null;
        for (EObject obj : outRes.getContents()) {
            if (linkCls.isInstance(obj)) {
                graphLink = obj;
                break;
            }
        }
        assertNotNull(graphLink, "Graph link not found");
        @SuppressWarnings("unchecked")
        EList<EObject> linkEntities = (EList<EObject>) graphLink.eGet(linkCls.getEStructuralFeature("Entitys"));
        assertEquals(2, linkEntities.size(), "Graph link should reference two entities");
    }
}