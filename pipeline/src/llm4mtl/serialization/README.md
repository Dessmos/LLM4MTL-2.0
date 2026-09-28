Two types of I/O, extracted from the modules that use them:

json_io.py         → reading and writing JSON, including "write once, or check the
                     file already holds the same content"
hashing.py         → file and folder hashes

There is no pipeline logic here at all. Just "how to correctly write to disk."

