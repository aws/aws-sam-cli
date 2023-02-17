build-HelloWorldFunction:
	echo "temp" >> file-created-from-makefile-function.txt
	cp *.py $(ARTIFACTS_DIR)
	cp requirements.txt $(ARTIFACTS_DIR)
	python -m pip install -r requirements.txt -t $(ARTIFACTS_DIR)
	rm -rf $(ARTIFACTS_DIR)/bin