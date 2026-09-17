package org.eclipse.epsilon.examples.etl;

import java.io.File;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.List;

import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.EcorePackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.EcoreResourceFactoryImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.eol.models.IModel;
import org.eclipse.epsilon.etl.EtlModule;
import org.junit.jupiter.api.AfterEach;

public abstract class EtlTestBase {

    protected EtlModule module;
    protected List<IModel> models = new ArrayList<>();

    static {
        // Register Ecore and XMI resource factories
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
            .putIfAbsent("ecore", new EcoreResourceFactoryImpl());
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
            .putIfAbsent("model", new XMIResourceFactoryImpl());
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
            .putIfAbsent("*", new XMIResourceFactoryImpl());
        // Ensure EcorePackage is initialized
        EcorePackage.eINSTANCE.eClass();
    }

    protected void registerMetamodel(String ecoreResourcePath) throws Exception {
        String absolutePath = getResourcePath(ecoreResourcePath);
        ResourceSet resourceSet = new ResourceSetImpl();
        resourceSet.getResourceFactoryRegistry().getExtensionToFactoryMap()
            .put("ecore", new EcoreResourceFactoryImpl());
        Resource resource = resourceSet.getResource(
            org.eclipse.emf.common.util.URI.createFileURI(absolutePath), true);
        resource.load(null);
        EPackage ePackage = (EPackage) resource.getContents().get(0);
        EPackage.Registry.INSTANCE.put(ePackage.getNsURI(), ePackage);
    }

    protected EmfModel createEmfModel(String name, String modelResourcePath,
            String metamodelUri, boolean readOnLoad, boolean storeOnDisposal) throws Exception {
        EmfModel model = new EmfModel();
        model.setName(name);
        model.setModelFileUri(org.eclipse.emf.common.util.URI.createFileURI(
            getResourcePath(modelResourcePath)));
        model.setMetamodelUri(metamodelUri);
        model.setReadOnLoad(readOnLoad);
        model.setStoredOnDisposal(storeOnDisposal);
        model.load();
        models.add(model);
        return model;
    }

    protected EmfModel createEmfModelFromFile(String name, String filePath,
            String metamodelUri, boolean readOnLoad, boolean storeOnDisposal) throws Exception {
        EmfModel model = new EmfModel();
        model.setName(name);
        model.setModelFileUri(org.eclipse.emf.common.util.URI.createFileURI(filePath));
        model.setMetamodelUri(metamodelUri);
        model.setReadOnLoad(readOnLoad);
        model.setStoredOnDisposal(storeOnDisposal);
        model.load();
        models.add(model);
        return model;
    }

    protected EtlModule runEtl(String etlResourcePath, IModel... modelArray) throws Exception {
        module = new EtlModule();
        module.parse(new File(getResourcePath(etlResourcePath)));

        if (module.getParseProblems().size() > 0) {
            throw new RuntimeException("ETL parse errors: " + module.getParseProblems());
        }

        for (IModel m : modelArray) {
            module.getContext().getModelRepository().addModel(m);
        }

        module.execute();
        return module;
    }

    protected String getResourcePath(String relativePath) throws Exception {
        java.net.URL url = getClass().getClassLoader().getResource(relativePath);
        if (url == null) {
            throw new IllegalArgumentException("Resource not found: " + relativePath);
        }
        return new File(url.toURI()).getAbsolutePath();
    }

    @AfterEach
    public void cleanup() {
        if (module != null) {
            module.getContext().getModelRepository().dispose();
            module.getContext().dispose();
        }
        models.clear();
    }
}
