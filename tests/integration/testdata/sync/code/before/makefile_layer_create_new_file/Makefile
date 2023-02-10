build-HelloWorldLayer:
	touch file-created-from-makefile-layer
	mkdir $(ARTIFACTS_DIR)/python
	cp *.py $(ARTIFACTS_DIR)/python
	cp requirements.txt $(ARTIFACTS_DIR)/python
	python -m pip install -r requirements.txt -t $(ARTIFACTS_DIR)/python
	rm -rf $(ARTIFACTS_DIR)/python/bin