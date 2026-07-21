package tools.vitruv.reactionsparser.utils;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

/**
 * Utility for loading all {@code *.ecore} files from a directory into the
 * global EMF {@link EPackage.Registry}.  This is necessary when parsing
 * reactions specifications that refer to custom meta-models.  Without
 * registering the corresponding EPackages the Xtext parser cannot resolve
 * references to the meta-model elements.
 */
public final class EcoreLoader {

    /**
     * Loads every {@code *.ecore} file in the supplied directory and
     * registers its contained {@link EPackage}s with the global registry.
     *
     * @param dir directory to scan for {@code *.ecore} files; if the
     *            parameter is {@code null} or not a directory, the call is
     *            ignored
     * @throws Exception if any of the files cannot be loaded
     */
    public static void loadAll(Path dir) throws Exception {
        if (dir == null || !Files.isDirectory(dir)) {
            return;
        }

        ResourceSet resourceSet = new ResourceSetImpl();
        try (Stream<Path> files = Files.walk(dir)) {
            files.filter(p -> p.toString().endsWith(".ecore"))
                    .forEach(p -> {
                        URI uri = URI.createFileURI(p.toAbsolutePath().toString());
                        Resource r = resourceSet.getResource(uri, true);
                        // Iterate over the contents and register any encountered EPackages.
                        r.getContents().stream()
                                .filter(EPackage.class::isInstance)
                                .map(EPackage.class::cast)
                                .forEach(pkg -> EPackage.Registry.INSTANCE.put(pkg.getNsURI(), pkg));
                    });
        }
    }

    // Prevent instantiation
    private EcoreLoader() {
    }
}