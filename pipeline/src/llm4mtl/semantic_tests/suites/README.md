General operations performed on the suite, treating it like a disk folder. These are used by both validation stages and the execution stage, which is why they have been factored out separately.



discovery.py - looks for suites and check who do they belong to
injection.py - put suite into engine
java.py      - decides where to put java files
metadata.py  — checks if suite should be started
