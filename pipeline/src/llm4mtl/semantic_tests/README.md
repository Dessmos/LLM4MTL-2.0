The semantic-test subsystem turns model output into deterministic, executable
JUnit suites and validates those suites before they can become an oracle.

The stages are:

1. `extraction/` parses file-oriented model output into `semantic_cases.json`
   and generated model files.
2. `codegen/` renders Java/JUnit deterministically.
3. `technical_validation/` compiles and smoke-runs the candidate suite.
4. `reference_validation/` checks the suite against the reference
   transformation.
5. `suites/` contains shared discovery, metadata, and injection primitives.

Active inputs live under:

    benchmark/tasks/<language>/{references,task_contracts}/
    prompt_assets/tests/{contract,few_shot,grammar,helper_methods}/<language>/

Generated prompts, raw responses, candidates, and validation results live under
`artifacts/work/test_generation/`. Each language's deterministic harness lives
under `engines/<language>/harness/`.



_init_.py                - says what is inside this folder
semantic_spec.py         - shared words about a test spec
scenario_mapping.py      - decides if this test can be described in the shared vocabulary?
validation.py            - checks if test works and if pass the reference validation
surefire.py              - checks what cause the problem, failed or real compile error
suite_execution.py       - run one test against one transformation, report the facts
execution_evidence.py    - save the evidence before the next run wipes it because of maven cleans it
diagnosis_preparation.py - gather everything needed to ask "test or transformation fault"