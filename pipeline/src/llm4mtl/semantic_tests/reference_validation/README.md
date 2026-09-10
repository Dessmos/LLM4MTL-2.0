In this stage we check if generated test can pass oracle validation


All possible results:

VALIDATED	                test pass oracle
REFERENCE_INVALID	        test doesn't pass oracle validation
NOT_EXECUTABLE	            test didn't start
ARTIFACT_INVALID	        doesn't compile


runner.py	        - entry point
cli.py	            - manual run
maven_status.py	55	- specific lines in MAVEN output
models.py	        - CSV columns
results.py	        - CSV by Task
reference.py	    - decides where to put working oracle


