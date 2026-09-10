This folder is an interface for all languages. All the differences between languages live here.

base.py             - interface that hides complexity with the methods that are really called by the pipeline
registry.py         - list of all suppoerted languages
common.py           - run the existing test and collect results
java_assertions.py  - create tests by taking generated information from json



by each language:

adapter.py          - realization of all methods from the interface. 
rendering.py        - generation of the test for the specific language