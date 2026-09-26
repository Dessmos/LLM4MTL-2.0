In this stage we check if generated test can pass oracle validation


All possible results:

VALIDATED	                test pass oracle
REFERENCE_INVALID	        test doesn't pass oracle validation
NOT_EXECUTABLE	            test could not run to the end (did not compile, crashed, timed out)
ARTIFACT_INVALID	        test files are not usable, so it was never run


runner.py	        - entry point
cli.py	            - manual run
maven_status.py	    - reads specific lines in the Maven output
models.py	        - CSV columns
results.py	        - CSV by Task
reference.py	    - decides where to put working oracle


