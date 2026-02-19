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

import mir.reactions.amaltheaToAscet.AmaltheaToAscetChangePropagationSpecification;
import tools.vitruv.change.propagation.ChangePropagationMode;
import tools.vitruv.change.testutils.TestUserInteraction;
import tools.vitruv.framework.views.CommittableView;
import tools.vitruv.framework.views.View;
import tools.vitruv.framework.views.ViewTypeFactory;
import tools.vitruv.framework.vsum.VirtualModel;
import tools.vitruv.framework.vsum.VirtualModelBuilder;
import tools.vitruv.framework.vsum.internal.InternalVirtualModel;
import tools.vitruv.methodologisttemplate.model.amalthea.AmaltheaFactory;
import tools.vitruv.methodologisttemplate.model.amalthea.ComponentContainer;
import tools.vitruv.methodologisttemplate.model.ascet.AscetModule;
import tools.vitruv.methodologisttemplate.model.ascet.InterruptTask;
import tools.vitruv.methodologisttemplate.model.ascet.PeriodicTask;


/**
 * VSUM Tests for Amalthea to Ascet Transformation
 */
public class UncorrectTaskNumberCreatesNoAscetModuleTest {

  @BeforeAll
  static void setup() {
    Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("*", new XMIResourceFactoryImpl());
  }

  @Test
  // reaction TaskCreated
  void uncorrectTaskNumberCreatesNoAscetModule(@TempDir Path tempDir) {
    TestUserInteraction testUserInteraction = new TestUserInteraction();
    // Choose task 5 (Unavailable)
    testUserInteraction.addNextSingleSelection(5);
    InternalVirtualModel vsum = new VirtualModelBuilder()
        .withStorageFolder(tempDir)
        .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(testUserInteraction))
        .withChangePropagationSpecifications(new AmaltheaToAscetChangePropagationSpecification())
        .buildAndInitialize();
    vsum.setChangePropagationMode(ChangePropagationMode.TRANSITIVE_CYCLIC);

    addComponentContainer(vsum, tempDir);
    modifyView(getDefaultView(vsum, List.of(ComponentContainer.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      var task = AmaltheaFactory.eINSTANCE.createTask();
      var componentContainer = v.getRootObjects(ComponentContainer.class).iterator().next();
      componentContainer.getTasks().add(task);
    });
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(ComponentContainer.class, AscetModule.class)), (View v) -> {
      return v.getRootObjects(ComponentContainer.class).iterator().next().getTasks().size() == 1
          && v.getRootObjects(AscetModule.class).iterator().next().getTasks().size() == 0;
    
    }));
  }

  // ==== helper methods ====

  private InternalVirtualModel createDefaultVirtualModel(Path projectPath) {
    InternalVirtualModel model = new VirtualModelBuilder()
        .withStorageFolder(projectPath)
        .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(new TestUserInteraction()))
        .withChangePropagationSpecifications(new AmaltheaToAscetChangePropagationSpecification())
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

  private void addComponentContainer(VirtualModel vsum, Path projectPath) {
    CommittableView view = getDefaultView(vsum, List.of(ComponentContainer.class)).withChangeDerivingTrait();
    modifyView(view, (CommittableView v) -> {
      ComponentContainer componentContainer = AmaltheaFactory.eINSTANCE.createComponentContainer();
      v.registerRoot(componentContainer,URI.createFileURI((projectPath.toString() + "/amalthea.amalthea")));
    });
  }

}