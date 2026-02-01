package tools.vitruv.methodologisttemplate.vsum;

import tools.vitruv.methodologisttemplate.model.families.FamilyRegister;
import tools.vitruv.methodologisttemplate.model.families.FamiliesFactory;
import tools.vitruv.methodologisttemplate.model.persons.PersonRegister;
import mir.reactions.familiesToPersons.FamiliesToPersonsChangePropagationSpecification;
import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.vitruv.change.propagation.ChangePropagationMode;
import tools.vitruv.change.testutils.TestUserInteraction;
import tools.vitruv.framework.views.CommittableView;
import tools.vitruv.framework.views.View;
import tools.vitruv.framework.views.ViewTypeFactory;
import tools.vitruv.framework.vsum.VirtualModel;
import tools.vitruv.framework.vsum.VirtualModelBuilder;
import tools.vitruv.framework.vsum.internal.InternalVirtualModel;

import java.nio.file.Path;
import java.util.Collection;
import java.util.List;
import java.util.function.Consumer;
import java.util.function.Function;

/**
 * VSUM Tests for Families to Persons Transformation
 */
public class InsertedDaughterCreatesPersonAndNamesAreCorrectTest {

  @BeforeAll
  static void setup() {
    Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("*", new XMIResourceFactoryImpl());
  }

  @Test
  // reaction InsertedDaughter
  void insertedDaughterCreatesPersonAndNamesAreCorrect(@TempDir Path tempDir) {
    InternalVirtualModel vsum = createDefaultVirtualModel(tempDir);
    addFamilyRegister(vsum, tempDir);
    addFamily(vsum);
    modifyView(getDefaultView(vsum, List.of(FamilyRegister.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      var daughter = FamiliesFactory.eINSTANCE.createMember();
      daughter.setFirstName("Jane");
      var family = v.getRootObjects(FamilyRegister.class).iterator().next().getFamilies().iterator().next();
      family.getDaughters().add(daughter);
    });
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(FamilyRegister.class, PersonRegister.class)), (View v) -> {
      // assert that exactly one family daughter and one person exists
      return v.getRootObjects(FamilyRegister.class).iterator().next()
        .getFamilies().get(0).getDaughters().size() == 1 &&
        v.getRootObjects(PersonRegister.class).iterator().next()
        .getPersons().size() == 1;
    }));
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(FamilyRegister.class, PersonRegister.class)), (View v) -> {
      // assert that the daughter's firstname is correct
      return v.getRootObjects(FamilyRegister.class).iterator().next()
        .getFamilies().get(0).getDaughters().get(0).getFirstName()
        .equals(v.getRootObjects(PersonRegister.class).iterator().next()
        .getPersons().get(0).getFullName().split(" ")[0]);
    }));
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(FamilyRegister.class, PersonRegister.class)), (View v) -> {
      // assert that the daughter's lastname is correct
      return v.getRootObjects(FamilyRegister.class).iterator().next()
        .getFamilies().get(0).getLastName()
        .equals(v.getRootObjects(PersonRegister.class).iterator().next()
        .getPersons().get(0).getFullName().split(" ")[1]);
    }));
  }



  // ==== helper methods ====
  private InternalVirtualModel createDefaultVirtualModel(Path projectPath) {
    InternalVirtualModel model = new VirtualModelBuilder()
        .withStorageFolder(projectPath)
        .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(new TestUserInteraction()))
        .withChangePropagationSpecifications(new FamiliesToPersonsChangePropagationSpecification())
        .buildAndInitialize();
    model.setChangePropagationMode(ChangePropagationMode.TRANSITIVE_CYCLIC);
    return model;
  }

  private View getDefaultView(VirtualModel vsum, Collection<Class<?>> rootTypes) {
    var selector = vsum.createSelector(ViewTypeFactory.createIdentityMappingViewType("default"));
    selector.getSelectableElements().stream()
        .filter(element -> rootTypes.stream().anyMatch(it -> it.isInstance(element)))
        .forEach(it -> selector.setSelected(it, true));
    return selector.createView();
  }

  private void modifyView(CommittableView view, Consumer<CommittableView> modificationFunction) {
    modificationFunction.accept(view);
    view.commitChanges();
  }

  private boolean assertView(View view, Function<View, Boolean> viewAssertionFunction) {
    return viewAssertionFunction.apply(view);
  }

  private void addFamilyRegister(VirtualModel vsum, Path projectPath) {
    CommittableView view = getDefaultView(vsum, List.of(FamilyRegister.class)).withChangeDerivingTrait();
    modifyView(view, (CommittableView v) -> {
      FamilyRegister reg = FamiliesFactory.eINSTANCE.createFamilyRegister();
      v.registerRoot(reg, URI.createFileURI(projectPath.toString() + "/families.families"));
    });
  }

  private void addFamily(VirtualModel vsum) {
    CommittableView view = getDefaultView(vsum, List.of(FamilyRegister.class)).withChangeDerivingTrait();
    modifyView(view, (CommittableView v) -> {
      var family = FamiliesFactory.eINSTANCE.createFamily();
      family.setLastName("Smith");
      v.getRootObjects(FamilyRegister.class).iterator().next().getFamilies().add(family);
    });
  }
}