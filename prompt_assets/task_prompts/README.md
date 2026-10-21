# Frozen task prompts

Each `<language>/<task>.txt` file is the single reviewed natural-language task
prompt used by both transformation generation and semantic-test generation.
These files were carried forward from the pre-refactor `main` workflows; they
are inputs to evaluation, not generated output.

Prompt-generation workflows write new candidates under
`artifacts/work/task_prompt_candidates/`. A candidate must be reviewed before
it replaces a file here. Downstream workflows never read the candidate
directory, so running prompt generation cannot silently change an experiment.

For every task, the filename stem must match the reference and task-contract
filename stem. The exact reference and metamodel contents are resolved through
the corresponding task contract; language-wide metamodel globs are forbidden.
