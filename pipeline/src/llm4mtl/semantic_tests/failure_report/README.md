Collects the information about failure
For each failure 1 JSON file

Standard case — Surefire identifies the method: `nodesArePreserved` failed with a specific error message. The dossier then covers that single test case—and, if an assertion failed, that specific assertion.

Early crash — the engine crashed before a single test could report back. There is nothing specific to name. In this case, the dossier covers the pair as a whole: this specific suite against this specific transformation—and that’s it.


To run manually: llm4mtl diagnosis report --request request.json --output .../failure-report.json


_init_.py       - interface of the folder
eligibility.py  - checks if report should be created and why
evidence.py     - collects facts for both variants of report
                    1. which execution do we describe
                    2. what do we know about the execution
request.py	    - checks what routes were mentioned
case_report.py	- report about one test-case
pair_report.py	- report about the pair
surefire_view.py	- takes data from XML files
artifacts.py	- read files from report
eligibility.py	- should we give this failure to the diagnosis
models.py	    - constants
cli.py	        - local start

