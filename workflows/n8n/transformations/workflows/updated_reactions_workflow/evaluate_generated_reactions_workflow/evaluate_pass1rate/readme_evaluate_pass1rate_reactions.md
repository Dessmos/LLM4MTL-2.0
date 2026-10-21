# Evaluate pass@1 rate for test cases for the Reactions Language Tasks.

To evaluate if the semantics of the generated reactions are correct, test-cases are executed.
However, to test one Reactions model transformation, in some cases also other model-transformations are required to create the desired model-state in the first place. 
Therefore, for these reactions, we use the correct "reference Reactions" and combine them with the LLM-generated Reaction. 
This way, we can ensure, that if the test fails, it is actually because the generated Reaction was faulty.

It is also possible, that the code, which belongs to the Reaction cannot be generated in the first place. This means, that the generated Reaction is not parsable => The test cannot be executed.

To configure, which "correct reference Reactions" must be combined with which task and which test cases, we provide the following JSON structure to configure that. The respective file-name is `task_to_test_cases_mapping_reactions.json`.

The workflow basically "builds" the project by copying the required reactions and test-cases into the template project.
Then the project is built and the test cases are executed. Afterwards the results are evaluated.

We assume, that the first entry in the required_imports_path_alias list is the model, where the reaction is triggered, while the second entry is the model where the Reaction makes changes after the trigger.

## Example configuration file

```json
[
  {
    "reaction_under_test": "FamiliesToPersons_CreatedFather",
    "required_correct_reactions_from_references": [
      "FamiliesToPersons_InsertedFamilyRegister"
    ],
    "testcases": [
      "CreatedFatherCreatesPersonAndNamesAreCorrectTest",
      "CreatedNewFatherRemovesOldFatherTest"
    ],
    "required_imports_path_alias": [{"http://vitruv.tools/methodologisttemplate/families":  "families"}, {"http://vitruv.tools/methodologisttemplate/persons": "persons"}],
    "name_of_generated_reaction": "familiesToPersons"
  },
  {
    "reaction_under_test": "FamiliesToPersons_DeletedFamily",
    "required_correct_reactions_from_references": [
      "FamiliesToPersons_InsertedFamilyRegister",
      "FamiliesToPersons_CreatedFather",
      "FamiliesToPersons_InsertedDaughter"
    ],
    "testcases": [
      "DeleteFamilyDeletesCorrespondingPersonsTest"
    ],
    "required_imports_path_alias": [{"http://vitruv.tools/methodologisttemplate/families":  "families"}, {"http://vitruv.tools/methodologisttemplate/persons": "persons"}],
    "name_of_generated_reaction": "familiesToPersons"
  },
]
```