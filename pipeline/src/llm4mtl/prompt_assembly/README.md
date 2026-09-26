in this folder files for n8n work

task_inputs.py      -   n8n asks via HTTP for a specific files.
                        POST /prompt-inputs/resolve  →  resolve_task_inputs(language, task)
                        by reading JSON files understand what n8n needs.
                        A custom task sends its own metamodel with the request:
                        POST /prompt-inputs/resolve {language, task, metamodel}
                          →  resolve_custom_task_inputs(...)
                        which consults no contract and no reference.

refinement.py       -   n8n asks via HTTP for the prompt of a retry after a failure.
                        POST /batches/{batch}/runs/{run}/refinements  →  prepare_refinement(...)
                        restates the task inputs the generation received, adds the
                        previous artifact and the recorded feedback, and writes
                        request.json + prompt.md into the run once.



n8n_exports/
            prompts.py	- text that each model gets
            workflow_graph.py - operations above n8n
            synchronizers.py  - what is rewritten in each prompt
            sync.py	 - which files must be rewritten
            main.py  - entry point for python -m sync


Called only by developer with 
            PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.prompt_assembly.n8n_exports --write

is needed if developer wants to change the prompts.py. To apply it faster to all n8n workflows this command should be used