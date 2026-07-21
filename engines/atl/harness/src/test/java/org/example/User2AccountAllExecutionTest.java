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
 * Integration test for the User->Account transformation.  The test
 * loads a User model with three users, runs the ATL module and verifies
 * that the resulting Account model contains the expected accounts with
 * correct active status based on user status.
 */
public class User2AccountAllExecutionTest {

    private ResourceSet rs;
    private EPackage userPkg;
    private EPackage accountPkg;

    @BeforeEach
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        userPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/User.ecore");
        accountPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Account.ecore");
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
    public void testUser2Account() throws Exception {
        File asm = compileAtl("User2Account_All.atl");
        File input = new File("src/main/resources/models", "user_input.xmi");
        assertTrue(input.exists(), "user_input.xmi not found: " + input.getAbsolutePath());

        EPackage.Registry.INSTANCE.put(userPkg.getNsURI(), userPkg);

        Resource outRes = executeAtl(asm, "User.ecore", "Account.ecore", "User", "Account", input);

        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass accountCls = (EClass) accountPkg.getEClassifier("Account");

        int accountCount = 0;
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (accountCls.isInstance(obj)) accountCount++;
        }
        assertEquals(3, accountCount, "Expected three Accounts");

        // Check each account
        boolean foundJohn = false;
        boolean foundJane = false;
        boolean foundBob = false;
        for (EObject obj : outRes.getContents()) {
            if (accountCls.isInstance(obj)) {
                String username = (String) obj.eGet(accountCls.getEStructuralFeature("username"));
                String email = (String) obj.eGet(accountCls.getEStructuralFeature("email"));
                Boolean active = (Boolean) obj.eGet(accountCls.getEStructuralFeature("active"));
                if ("john_doe".equals(username)) {
                    foundJohn = true;
                    assertEquals("john@example.com", email);
                    assertTrue(active, "john_doe should be active");
                } else if ("jane_smith".equals(username)) {
                    foundJane = true;
                    assertEquals("jane@example.com", email);
                    assertTrue(active, "jane_smith should be active");
                } else if ("bob_wilson".equals(username)) {
                    foundBob = true;
                    assertEquals("bob@example.com", email);
                    assertFalse(active, "bob_wilson should not be active");
                }
            }
        }
        assertTrue(foundJohn, "Account 'john_doe' missing");
        assertTrue(foundJane, "Account 'jane_smith' missing");
        assertTrue(foundBob, "Account 'bob_wilson' missing");
    }
}
