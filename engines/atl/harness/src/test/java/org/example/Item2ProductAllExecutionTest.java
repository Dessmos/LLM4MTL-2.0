package org.example;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.io.FileReader;
import java.io.Reader;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

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
 * Integration test for the Item->Product transformation.  The test
 * loads an Item model with three items (Laptop, T-Shirt, Book),
 * runs the ATL module and verifies that the resulting Product model
 * contains the expected products with correct category and inStock values.
 */
public class Item2ProductAllExecutionTest {

    private ResourceSet rs;
    private EPackage itemPkg;
    private EPackage productPkg;

    @BeforeEach
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        itemPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Item.ecore");
        productPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Product.ecore");
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
    public void testItem2Product() throws Exception {
        File asm = compileAtl("Item2Product_All.atl");
        File input = new File("src/main/resources/models", "item_input.xmi");
        assertTrue(input.exists(), "item_input.xmi not found: " + input.getAbsolutePath());

        EPackage.Registry.INSTANCE.put(itemPkg.getNsURI(), itemPkg);

        Resource outRes = executeAtl(asm, "Item.ecore", "Product.ecore", "Item", "Product", input);

        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass productCls = (EClass) productPkg.getEClassifier("Product");

        int productCount = 0;
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (productCls.isInstance(obj)) productCount++;
        }
        assertEquals(3, productCount, "Expected three Products");

        // Check each product
        boolean foundLaptop = false;
        boolean foundTShirt = false;
        boolean foundBook = false;
        for (EObject obj : outRes.getContents()) {
            if (productCls.isInstance(obj)) {
                String name = (String) obj.eGet(productCls.getEStructuralFeature("name"));
                String category = (String) obj.eGet(productCls.getEStructuralFeature("category"));
                Boolean inStock = (Boolean) obj.eGet(productCls.getEStructuralFeature("inStock"));
                Double price = (Double) obj.eGet(productCls.getEStructuralFeature("price"));
                if ("Laptop".equals(name)) {
                    foundLaptop = true;
                    assertEquals("Tech", category, "Laptop category should be Tech");
                    assertTrue(inStock, "Laptop should be in stock");
                    assertEquals(999.99, price, 0.01, "Laptop price");
                } else if ("T-Shirt".equals(name)) {
                    foundTShirt = true;
                    assertEquals("Apparel", category, "T-Shirt category should be Apparel");
                    assertFalse(inStock, "T-Shirt should not be in stock");
                    assertEquals(19.99, price, 0.01, "T-Shirt price");
                } else if ("Book".equals(name)) {
                    foundBook = true;
                    assertEquals("General", category, "Book category should be General");
                    assertTrue(inStock, "Book should be in stock");
                    assertEquals(29.99, price, 0.01, "Book price");
                }
            }
        }
        assertTrue(foundLaptop, "Product 'Laptop' missing");
        assertTrue(foundTShirt, "Product 'T-Shirt' missing");
        assertTrue(foundBook, "Product 'Book' missing");
    }
}
