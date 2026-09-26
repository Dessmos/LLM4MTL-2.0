This folder is an interface for all languages. All the differences between languages live here.

base.py             - interface that hides complexity with the methods that are really called by the pipeline
registry.py         - list of all supported languages
common.py           - shared adapter steps: run the parser, run the test, collect results
java_assertions.py  - create tests by taking generated information from json
java_resources.py   - read the fixed Java text kept in the java/ folders
java/               - fixed Java text shared by the ATL, QVT-O and Reactions harnesses



by each language:

adapter.py          - realization of all methods from the interface.
rendering.py        - generation of the test for the specific language
java/               - fixed Java text that rendering.py copies into the test
reactions/prerequisites.py - reactions a Reactions task needs, merged into the file under test