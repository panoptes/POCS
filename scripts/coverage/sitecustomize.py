# Ensure coverage starts for all Python processes so that test coverage is calculated
# properly when using subprocesses (see https://coverage.readthedocs.io/en/latest/subprocess.html)
import coverage
print("Starting coverage from sitecustomize")
coverage.process_startup()
