build-Function:
	cp ./custom_src_code/*.py $(ARTIFACTS_DIR)
	cp ./custom_src_code/requirements.txt $(ARTIFACTS_DIR)
	python -m pip install -r ./custom_src_code/requirements.txt -t $(ARTIFACTS_DIR)
	rm -rf $(ARTIFACTS_DIR)/bin