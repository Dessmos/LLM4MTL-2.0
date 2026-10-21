where the Java code executes, so that the runs do not interfere with each other.

materialization.py  - It copies the engine template to `runs/<batch>/<run>/workspaces/etl/`. 
                        Each run operates within its own copy.
injection.py        - put temporary files in one folder for the execution and then clear it
