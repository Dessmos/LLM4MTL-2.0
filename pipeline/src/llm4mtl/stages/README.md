The Python stages. n8n starts them through stage_service, the local
experiment_runner can start them too. Both look a stage up in dispatch.py.

_init_.py                   - says what is inside this folder
models.py                   - Data classes and contracts. Contains no logic
                                PipelineConfig - all what one run describes
                                StageResult    - Result of one stage
                                ConfigError    - the config breaks the run contract
dispatch.py                 - which code runs which stage (extract, syntax-validation,
                              technical-validation, reference-validation, execution)
                              and which stages need their own copy of the engine
test_generation.py          - extract, technical-validation, reference-validation
transformation_parser.py    - syntax-validation of generated transformations
transformation_validation.py- execution: run validated tests against generated transformations
selection.py                - pick the inputs of a stage and hash them
