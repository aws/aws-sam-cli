SHELL := /bin/bash
PY_VERSION := 3.6

export PYTHONUNBUFFERED := 1

export AWS_PROFILE := sandbox
STACK_NAME := stack-cloudschedule

BASE := $(shell /bin/pwd)
VENV_DIR := $(BASE)/.venv
export PATH := var:$(PATH):$(VENV_DIR)/bin

PYTHON := $(shell /usr/bin/which python$(PY_VERSION))
VIRTUALENV := $(PYTHON) -m venv
ZIP_FILE := $(BASE)/bundle.zip

.DEFAULT_GOAL := build
.PHONY: build clean release describe deploy package bundle bundle.local


build:
	$(VIRTUALENV) "$(VENV_DIR)"
	"$(VENV_DIR)/bin/pip$(PY_VERSION)" \
		--isolated \
		--disable-pip-version-check \
		install -Ur requirements.txt

bundle.local:
	zip -r -9 "$(ZIP_FILE)" example
	cd "$(VENV_DIR)/lib/python$(PY_VERSION)/site-packages" \
		&& zip -r9 "$(ZIP_FILE)" *
	cd "$(VENV_DIR)/lib64/python$(PY_VERSION)/site-packages" \
		&& zip -r9 "$(ZIP_FILE)" *

bundle:
	docker run -v $$PWD:/var/task -it lambci/lambda:build-python3.6 /bin/bash -c 'make clean build bundle.local'

package:
	sam package \
		--template-file template.yml \
		--s3-bucket fridev-lambda \
		--s3-prefix sources \
		--output-template-file packaged.yml

deploy:
	sam deploy \
		--template-file packaged.yml \
		--stack-name $(STACK_NAME) \
		--capabilities CAPABILITY_IAM

# call this in case of errors
describe:
	aws cloudformation describe-stack-events --stack-name $(STACK_NAME)

release:
	@make bundle
	@make package
	@make deploy

clean:
	rm -rf "$(VENV_DIR)" "$(BASE)/var" "$(BASE)/__pycache__" "$(ZIP_FILE)"

