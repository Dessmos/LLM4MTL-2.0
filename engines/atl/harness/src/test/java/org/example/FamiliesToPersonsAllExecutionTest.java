package org.example;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.io.FileReader;
import java.io.Reader;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

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
 * Integration test for the combined Families→Persons transformation.  The test
 * loads the concrete families model, runs the ATL module and
 * asserts that the resulting Persons model contains the expected number of
 * male and female persons as well as the correct full names.
 */
public class FamiliesToPersonsAllExecutionTest {

    private ResourceSet rs;
    private EPackage familiesPkg;
    private EPackage personsPkg;

    @BeforeEach
    // Initialize a new resource set and load the Amalthea and Ascet metamodels.
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        familiesPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/families.ecore");
        personsPkg    = loadAndRegisterEcore(rs, "src/main/resources/metamodels/persons.ecore");
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
    public void testFamiliesToPersons() throws Exception {
        // Compile the ATL module
        File asm = compileAtl("FamiliesToPersons_All.atl");
        // Load the sample input model from the resources folder.
        File input = new File("src/main/resources/models", "families_input.xmi");
        assertTrue(input.exists(), "families_input.xmi not found: " + input.getAbsolutePath());

        // Register the Families metamodel in the global package registry.
        // The ATL injector will use this to resolve the namespace when loading the input XMI.
        EPackage.Registry.INSTANCE.put(familiesPkg.getNsURI(), familiesPkg);

        // Execute the transformation using the input file
        Resource outRes = executeAtl(asm, "families.ecore", "persons.ecore", "Families", "Persons", input);
        
        // Verify the resulting Persons model.
        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass maleCls = (EClass) personsPkg.getEClassifier("Male");
        EClass femaleCls = (EClass) personsPkg.getEClassifier("Female");
        int maleCount = 0;
        int femaleCount = 0;
        for (EObject obj : outRes.getContents()) {
            if (maleCls.isInstance(obj)) maleCount++;
            if (femaleCls.isInstance(obj)) femaleCount++;
        }
        assertEquals(5, maleCount, "Expected 5 male persons");
        assertEquals(4, femaleCount, "Expected 4 female persons");
        // Check that each created Person has one of the expected full names.
        EClass personCls = (EClass) personsPkg.getEClassifier("Person");
        for (EObject obj : outRes.getContents()) {
            if (maleCls.isInstance(obj) || femaleCls.isInstance(obj)) {
                String fullName = (String) obj.eGet(personCls.getEStructuralFeature("fullName"));
                assertTrue(
                    fullName.equals("Jim March") ||
                    fullName.equals("Brandon March") ||
                    fullName.equals("Peter Sailor") ||
                    fullName.equals("David Sailor") ||
                    fullName.equals("Dylan Sailor") ||
                    fullName.equals("Cindy March") ||
                    fullName.equals("Brenda March") ||
                    fullName.equals("Jackie Sailor") ||
                    fullName.equals("Kelly Sailor"),
                    "Unexpected fullName: " + fullName
                );
            }
        }
    }
}