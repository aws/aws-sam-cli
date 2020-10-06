build-HelloWorldFunction:
	cp *.py $(ARTIFACTS_DIR)
	cp empty-requirements.txt $(ARTIFACTS_DIR)
	python -m pip install -r empty-requirements.txt -t $(ARTIFACTS_DIR)
	rm -rf $(ARTIFACTS_DIR)/bin

build-HelloMarsFunction:
	cp *.py $(ARTIFACTS_DIR)
	cp requests-requirements.txt $(ARTIFACTS_DIR)
	python -m pip install -r requests-requirements.txt -t $(ARTIFACTS_DIR)
	rm -rf $(ARTIFACTS_DIR)/bin