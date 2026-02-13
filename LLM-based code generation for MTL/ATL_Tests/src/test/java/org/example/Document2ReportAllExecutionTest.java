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
 * Integration test for the Document->Report transformation.  The test
 * loads a Document model with one document containing three sections,
 * runs the ATL module and verifies the resulting Report model.
 */
public class Document2ReportAllExecutionTest {

    private ResourceSet rs;
    private EPackage documentPkg;
    private EPackage reportPkg;

    @BeforeEach
    public void initResourceSet() {
        rs = new ResourceSetImpl();
        documentPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Document.ecore");
        reportPkg = loadAndRegisterEcore(rs, "src/main/resources/metamodels/Report.ecore");
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
    public void testDocument2Report() throws Exception {
        File asm = compileAtl("Document2Report_All.atl");
        File input = new File("src/main/resources/models", "document_input.xmi");
        assertTrue(input.exists(), "document_input.xmi not found: " + input.getAbsolutePath());

        EPackage.Registry.INSTANCE.put(documentPkg.getNsURI(), documentPkg);

        Resource outRes = executeAtl(asm, "Document.ecore", "Report.ecore", "Document", "Report", input);

        assertTrue(!outRes.getContents().isEmpty(), "Output model is empty");

        EClass reportCls = (EClass) reportPkg.getEClassifier("Report");
        EClass sectionCls = (EClass) reportPkg.getEClassifier("Section");

        int reportCount = 0;
        int sectionCount = 0;
        for (TreeIterator<EObject> it = outRes.getAllContents(); it.hasNext(); ) {
            EObject obj = it.next();
            if (reportCls.isInstance(obj)) reportCount++;
            if (sectionCls.isInstance(obj)) sectionCount++;
        }
        assertEquals(1, reportCount, "Expected one Report");
        assertEquals(3, sectionCount, "Expected three Sections");

        // Find the Report and check its attributes
        EObject report = null;
        for (EObject obj : outRes.getContents()) {
            if (reportCls.isInstance(obj)) {
                report = obj;
                break;
            }
        }
        assertNotNull(report, "Report object not found");
        assertEquals("Project Report", report.eGet(reportCls.getEStructuralFeature("title")));
        assertEquals("John Doe", report.eGet(reportCls.getEStructuralFeature("author")));

        // Check sections
        @SuppressWarnings("unchecked")
        EList<EObject> sections = (EList<EObject>) report.eGet(reportCls.getEStructuralFeature("sections"));
        assertEquals(3, sections.size(), "Report should have three sections");
        boolean foundIntro = false;
        boolean foundMethodology = false;
        boolean foundConclusion = false;
        for (EObject s : sections) {
            String title = (String) s.eGet(sectionCls.getEStructuralFeature("title"));
            if ("Introduction".equals(title)) foundIntro = true;
            if ("Methodology".equals(title)) foundMethodology = true;
            if ("Conclusion".equals(title)) foundConclusion = true;
        }
        assertTrue(foundIntro, "Section 'Introduction' missing");
        assertTrue(foundMethodology, "Section 'Methodology' missing");
        assertTrue(foundConclusion, "Section 'Conclusion' missing");
    }
}
