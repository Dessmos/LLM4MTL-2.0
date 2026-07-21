package tools.vitruv.reactionsparser.cli;

import tools.vitruv.reactionsparser.parser.GenericXtextParser;
import tools.vitruv.reactionsparser.utils.EcoreLoader;
import tools.vitruv.dsls.reactions.ReactionsLanguageStandaloneSetup;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.eclipse.xtext.validation.Issue;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

/**
 * Command line entry point for parsing reactions DSL files.  The parser
 * accepts one required input file and one required output file.  An
 * optional third argument specifies the directory containing {@code *.ecore}
 * files.  If omitted, the directory of the input file is used to locate
 * meta-model definitions.
 *
 * <p>
 * Usage:
 * <pre>
 *   java -jar reactions-parser-0.1.0-SNAPSHOT-all.jar <input.reactions> <output.xmi> [<ecoreDir>]
 * </pre>
 * If parsing fails due to syntax problems, the program prints the number
 * of errors along with a short description for each and terminates with
 * a non-zero exit code.  On success, the parsed model is saved as XMI
 * and "Parsed OK" is printed to stdout.
 * </p>
 */
public class ReactionsCli {

    /**
     * Saves the given EMF model to an XMI file at the provided path.  The
     * XMI resource factory is registered on demand to avoid global side
     * effects.
     *
     * @param content root object of the model to save
     * @param path    file system location where the XMI should be written
     * @throws IOException if saving the resource fails
     */
    private static void save(EObject content, String path) throws IOException {
        // Ensure the XMI factory is registered for the "xmi" extension.
        Resource.Factory.Registry reg = Resource.Factory.Registry.INSTANCE;
        Map<String, Object> m = reg.getExtensionToFactoryMap();
        m.put("xmi", new XMIResourceFactoryImpl());

        ResourceSet resSet = new ResourceSetImpl();
        Resource resource = resSet.createResource(URI.createURI(path));
        resource.getContents().add(content);
        resource.save(Map.of());
    }

    /**
     * Main method invoked by the JVM when running the shaded JAR.  Performs
     * argument validation, bootstraps the reactions language, loads any
     * user-specified meta-models, parses the input file, reports issues and
     * saves the model.
     */
    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) {
            System.err.println("Usage: java -jar <jar> <in.reactions> <out.xmi> [ecoreDir]");
            System.exit(1);
        }

        // Initialise Xtext for the reactions language.  This call sets up
        // dependency injection and registers the language's resource service
        // provider with the global registry.
        ReactionsLanguageStandaloneSetup.doSetup();

        // Determine directory to scan for *.ecore files.  If an explicit
        // directory is given use that, otherwise look in the directory
        // containing the input file.  This allows relative references
        // between the reactions specification and its meta-model.
        Path ecoreDir = args.length == 3 ? Paths.get(args[2]) : Paths.get(args[0]).getParent();
        EcoreLoader.loadAll(ecoreDir);

        // Parse the input file and validate it.  The parser returns both
        // the resulting model and the list of validation issues (syntax or
        // unresolved references).  If any issues are present, print them
        // and abort with exit code 1.
        GenericXtextParser parser = new GenericXtextParser();
        GenericXtextParser.ParseResult result = parser.parse(args[0]);
        List<Issue> issues = result.getIssues();

        if (!issues.isEmpty()) {
            System.err.println("Syntax issues (" + issues.size() + "):");
            for (Issue issue : issues) {
                // Include severity to help users distinguish errors from warnings.
                System.err.println(issue.getMessage() + " (" + issue.getSeverity() + ")");
            }
            // Fail fast on any issues.  The specification requires that
            // syntax errors cause the program to exit with a non-zero status.
            System.exit(1);
        }

        // Persist the model as an XMI file.  On success print a friendly
        // message with the absolute path to the output file.
        save(result.getRoot(), args[1]);
        System.out.println("Parsed OK → " + Paths.get(args[1]).toAbsolutePath());
    }
}