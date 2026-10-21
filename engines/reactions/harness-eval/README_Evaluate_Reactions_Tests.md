# Project purpose
This maven project is a copy of the Reactions_Language_Tests project, which contains the original test-cases, reference reactions files and the required meta-models.

The present project is simply used by the evaluation workflow to inject LLM-generated reactions-files, build the project and if this succeeds, run the tests.
The evaluation script, which triggers this workflow is defined under ```natural-language-artifacts/LLM-based code generation for MTL/Workflows/n8n-docker/workflows/updated_reactions_workflow/evaluate_generated_reactions_workflow```.