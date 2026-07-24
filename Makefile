PYTHON ?= python3
PYTHONPATH := src

.PHONY: demo test lint reproduce-benchmark reproduce-counterfactuals

demo:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m culprit demo
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m culprit investigate --live --quiet
	@echo "CULPRIT replay and live CPU descent completed."

test:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

lint:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q src tests
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m culprit check

reproduce-benchmark:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m culprit reproduce-benchmark

reproduce-counterfactuals:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m culprit reproduce-counterfactuals

