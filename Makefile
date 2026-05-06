.PHONY: check

check:
	python -m compileall -q src tests
	PYTHONPATH=src python -m unittest discover -s tests/unit
