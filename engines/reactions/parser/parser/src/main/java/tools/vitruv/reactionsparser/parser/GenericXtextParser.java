package tools.vitruv.reactionsparser.parser;

import java.util.List;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.xtext.resource.IResourceServiceProvider;
import org.eclipse.xtext.resource.XtextResource;
import org.eclipse.xtext.util.CancelIndicator;
import org.eclipse.xtext.validation.CheckMode;
import org.eclipse.xtext.validation.Issue;

/**
 * A thin wrapper around Xtext's resource loading and validation APIs that
 * exposes both the parsed model as well as the list of validation issues.
 *
 * <p>
 * The reactions language is built with Xtext and therefore registers an
 * {@link IResourceServiceProvider} for files with the {@code .reactions}
 * extension.  This parser delegates to the registered provider to load
 * and validate a given file.  After loading, the parsed model can be
 * retrieved via the {@link ParseResult#getRoot()} method and any syntax
 * or validation problems via {@link ParseResult#getIssues()}.
 * </p>
 */
public class GenericXtextParser {

    /**
     * Parses the file at the given path into an EMF model.  This method
     * performs a fast-only validation of the resource and returns the
     * resulting root object together with the list of issues discovered
     * during parsing.
     *
     * @param path absolute or relative file system path to the reactions file
     * @return a result containing the parsed root and any validation issues
     * @throws Exception if the resource cannot be loaded
     */
    public ParseResult parse(String path) throws Exception {
        // Obtain the appropriate resource service provider based on the file URI.
        var resourceServiceProvider = IResourceServiceProvider.Registry.INSTANCE
                .getResourceServiceProvider(URI.createFileURI(path));

        // Xtext uses dependency injection to create the ResourceSet.  The
        // provider supplies an instance when asked for the ResourceSet.class.
        ResourceSet resourceSet = resourceServiceProvider.get(ResourceSet.class);

        // Load the resource.  Passing 'true' indicates that the resource
        // should be loaded on demand if it is not already present in the set.
        var resource = resourceSet.getResource(URI.createFileURI(path), true);

        // Validate the resource using FAST_ONLY mode to catch syntax errors
        // without performing expensive full analysis.  CancelIndicator.NullImpl
        // indicates that validation should not be cancelled.
        var validator = ((XtextResource) resource).getResourceServiceProvider().getResourceValidator();
        List<Issue> issues = validator.validate(resource, CheckMode.FAST_ONLY, CancelIndicator.NullImpl);

        // Retrieve the first root element from the resource.  Reactions files
        // always have a single root, so index 0 is sufficient.
        EObject root = (EObject) resource.getContents().get(0);

        return new ParseResult(root, issues);
    }

    /**
     * Container type returned from {@link #parse(String)} containing both
     * the parsed model root and the list of validation issues.
     */
    public static final class ParseResult {
        private final EObject root;
        private final List<Issue> issues;

        public ParseResult(EObject root, List<Issue> issues) {
            this.root = root;
            this.issues = issues;
        }

        /**
         * Returns the root element of the parsed EMF model.
         */
        public EObject getRoot() {
            return root;
        }

        /**
         * Returns the list of issues found during validation.  The list is
         * immutable; changes to it will not affect the stored issues.  If
         * parsing succeeded without any problems the list will be empty.
         */
        public List<Issue> getIssues() {
            return issues;
        }
    }
}