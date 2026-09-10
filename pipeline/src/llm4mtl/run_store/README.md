This is a "save" place for one run. Everything what run writes and rules how to do it.

models.py           - have information where what stores
identity.py         - check that a run id is safe and cannot escape its folder
manifest.py         - write who this run is, once, and never change it
events.py           - append what happened, line by line
attempts.py         - give every new attempt its own number
stages.py           - store the result of each stage attempt
batches.py          - create the batch and save runs of one batch inside
results.py          - write how the run has ended
transformations.py  - copy the judged transformation into the run, so it cannot change
generations.py      - record every call to an LLM
refinements.py      - build the input for a retry in the loop after a failure
responses.py        - store the diagnosis verdict