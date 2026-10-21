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
public class AmaltheaAscetTest {

  @BeforeAll
  static void setup() {
    Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("*", new XMIResourceFactoryImpl());
  }

  @Test
  // reaction ComponentContainerInsertedAsRoot
  void ComponentContainerInsertedAsRootCreatesRootcomponentcontainer(@TempDir Path tempDir) {
    VirtualModel vsum = createDefaultVirtualModel(tempDir);
    addComponentContainer(vsum, tempDir);
    Assertions.assertEquals(1, getDefaultView(vsum, List.of(ComponentContainer.class)).getRootObjects().size());
    Assertions.assertEquals(1, getDefaultView(vsum, List.of(AscetModule.class)).getRootObjects().size());
  }

  @Test
  // reaction TaskCreated
  void InterruptTaskCreatedCreatesAscetModule(@TempDir Path tempDir) {
    TestUserInteraction testUserInteraction = new TestUserInteraction();
    // Choose task 0 (InterruptTask)
    testUserInteraction.addNextSingleSelection(0);
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
          && v.getRootObjects(AscetModule.class).iterator().next().getTasks().size() == 1;
    }));
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(ComponentContainer.class, AscetModule.class)), (View v) -> {
      return v.getRootObjects(AscetModule.class).iterator().next().getTasks().get(0) instanceof InterruptTask;
    }));
  }


    @Test
  // reaction TaskCreated
  void PeriodicTaskCreatedCreatesAscetModule(@TempDir Path tempDir) {
    TestUserInteraction testUserInteraction = new TestUserInteraction();
    // Choose task 1 (PeriodicTask)
    testUserInteraction.addNextSingleSelection(1);
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
          && v.getRootObjects(AscetModule.class).iterator().next().getTasks().size() == 1;
    }));
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(ComponentContainer.class, AscetModule.class)), (View v) -> {
      return v.getRootObjects(AscetModule.class).iterator().next().getTasks().get(0) instanceof PeriodicTask;
    }));
  }

  @Test
  // reaction TaskCreated
  void UncorrectTaskNumberCreatesNoAscetModule(@TempDir Path tempDir) {
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

  @Test
  // reaction TaskDeleted
  void TaskDeletedRemovesCorrespondingAscetTask(@TempDir Path tempDir) {
    TestUserInteraction testUserInteraction = new TestUserInteraction();

    testUserInteraction.addNextSingleSelection(0);
    
    InternalVirtualModel vsum = new VirtualModelBuilder().withStorageFolder(tempDir).withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(testUserInteraction))
    .withChangePropagationSpecification(new AmaltheaToAscetChangePropagationSpecification())
    .buildAndInitialize();

    // Create the root Container first
    addComponentContainer(vsum, tempDir);
    // Add a Task => Triggers TaskCreated (and creates a corresponding Ascet::Task)
    modifyView(getDefaultView(vsum, List.of(ComponentContainer.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      var task = AmaltheaFactory.eINSTANCE.createTask();
      var componentContainer = v.getRootObjects(ComponentContainer.class).iterator().next();
      componentContainer.getTasks().add(task);
    });

    // Sanity check: Check that both tasks are created accordingly.
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(ComponentContainer.class, AscetModule.class)), (View v) -> {
      return v.getRootObjects(ComponentContainer.class).iterator().next().getTasks().size() == 1
        && v.getRootObjects(AscetModule.class).iterator().next().getTasks().size() == 1;
    }));

    modifyView(getDefaultView(vsum, List.of(ComponentContainer.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      var componentContainer = v.getRootObjects(ComponentContainer.class).iterator().next();
      var taskToDelete = componentContainer.getTasks().get(0);
      componentContainer.getTasks().remove(taskToDelete);
    });

    // Assert deletion propagated: both sides have zero tasks again
    Assertions.assertTrue(assertView(getDefaultView(vsum, List.of(ComponentContainer.class, AscetModule.class)), (View v) -> {
      boolean componentContainerTasksIsEmpty = v.getRootObjects(ComponentContainer.class).iterator().next().getTasks().isEmpty();
      boolean ascetModuleTasksIsEmpty = v.getRootObjects(AscetModule.class).iterator().next().getTasks().isEmpty();
      System.out.println("componentContainerTasksIsEmpty: " + componentContainerTasksIsEmpty);
      System.out.println("ascetModuleTasksIsEmpty: " + ascetModuleTasksIsEmpty);
      return v.getRootObjects(ComponentContainer.class).iterator().next().getTasks().isEmpty()
        && v.getRootObjects(AscetModule.class).iterator().next().getTasks().isEmpty();
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