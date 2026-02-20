package tools.vitruv.methodologisttemplate.vsum;

import java.nio.file.Path;
import java.util.Collection;
import java.util.List;
import java.util.function.Consumer;
import java.util.function.Function;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import mir.reactions.combinedReactions.CombinedReactionsChangePropagationSpecification;
import tools.vitruv.change.propagation.ChangePropagationMode;
import tools.vitruv.change.testutils.TestUserInteraction;
import tools.vitruv.framework.views.CommittableView;
import tools.vitruv.framework.views.View;
import tools.vitruv.framework.views.ViewTypeFactory;
import tools.vitruv.framework.vsum.VirtualModel;
import tools.vitruv.framework.vsum.VirtualModelBuilder;
import tools.vitruv.framework.vsum.internal.InternalVirtualModel;
import tools.vitruv.methodologisttemplate.model.families.FamiliesFactory;
import tools.vitruv.methodologisttemplate.model.families.FamilyRegister;
import tools.vitruv.methodologisttemplate.model.persons.PersonRegister;

/**
 * VSUM Tests for Families to Persons Transformation
 */
public class DeleteFatherDeletesCorrespondingPersonTest {

  @BeforeAll
  static void setup() {
    Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("*", new XMIResourceFactoryImpl());
  }

  @Test
  // reaction DeletedFamily
  void deleteFamilyDeletesCorrespondingPersons(@TempDir Path tempDir) {
    InternalVirtualModel vsum = createDefaultVirtualModel(tempDir);
    addFamilyRegister(vsum, tempDir);
    addFamily(vsum);
    modifyView(getDefaultView(vsum, List.of(FamilyRegister.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      var family = v.getRootObjects(FamilyRegister.class).iterator().next().getFamilies().iterator().next();
      var father = FamiliesFactory.eINSTANCE.createMember();
      father.setFirstName("John");
      family.setFather(father);
      var daughter = FamiliesFactory.eINSTANCE.createMember();
      daughter.setFirstName("Jane");
      family.getDaughters().add(daughter);
    });
    modifyView(getDefaultView(vsum, List.of(FamilyRegister.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      v.getRootObjects(FamilyRegister.class).iterator().next().getFamilies().remove(0);
    });
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(FamilyRegister.class, PersonRegister.class)), (View v) -> {
      // assert that all persons are deleted
      return v.getRootObjects(PersonRegister.class).iterator().next().getPersons().isEmpty();
    }));
  }



  // ==== helper methods ====
  private InternalVirtualModel createDefaultVirtualModel(Path projectPath) {
    InternalVirtualModel model = new VirtualModelBuilder()
        .withStorageFolder(projectPath)
        .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(new TestUserInteraction()))
        .withChangePropagationSpecifications(new CombinedReactionsChangePropagationSpecification())
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