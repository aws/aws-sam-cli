# Default value for environment variable. Can be overridden by setting the
# environment variable.
SAM_CLI_TELEMETRY ?= 0

.PHONY: schema

init:
	SAM_CLI_DEV=1 pip install -e '.[dev]'

test:
	# Run unit tests
	# Fail if coverage falls below 95%
	pytest --cov samcli --cov schema --cov-report term-missing --cov-fail-under 94 tests/unit

test-cov-report:
	# Run unit tests with html coverage report
	pytest --cov samcli --cov schema --cov-report html --cov-fail-under 94 tests/unit

integ-test:
	# Integration tests don't need code coverage
	@echo Telemetry Status: $(SAM_CLI_TELEMETRY)
	SAM_CLI_DEV=1 pytest tests/integration

func-test:
	# Verify function test coverage only for `samcli.local` package
	@echo Telemetry Status: $(SAM_CLI_TELEMETRY)
	pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional

regres-test:
	@echo Telemetry Status: $(SAM_CLI_TELEMETRY)
	SAM_CLI_DEV=1 pytest tests/regression

smoke-test:
	# Smoke tests run in parallel
	SAM_CLI_DEV=1 pytest -n 4 tests/smoke

lint:
	# Linter performs static analysis to catch latent bugs
	ruff samcli schema
	# mypy performs type check
	mypy --exclude /testdata/ --exclude /init/templates/ --no-incremental setup.py samcli tests schema

# Command to run everytime you make changes to verify everything works
dev: lint test

black:
	black setup.py samcli tests schema

black-check:
	black --check setup.py samcli tests schema

format: black
	ruff samcli --fix

schema:
	python -m schema.make_schema

# Verifications to run before sending a pull request
pr: init dev schema black-check

# (jfuss) We updated to have two requirement files, one for mac and one for linux. This
# is meant to be a short term fix when upgrading the Linux installer to be python3.11 from 
# python3.7. Having different requirements is not ideal but this allows us to isolate changes
# giving us the ability to roll out upgrade to Linux first. When we update the MacOS installer
# we can move to a single file again.
update-reproducible-linux-reqs:
	python3.11 -m venv venv-update-reproducible-linux
	venv-update-reproducible-linux/bin/pip install --upgrade pip-tools pip
	venv-update-reproducible-linux/bin/pip install -r requirements/base.txt
	venv-update-reproducible-linux/bin/pip-compile --generate-hashes --allow-unsafe -o requirements/reproducible-linux.txt

update-reproducible-mac-reqs:
	python3.8 -m venv venv-update-reproducible-mac
	venv-update-reproducible-mac/bin/pip install --upgrade pip-tools pip
	venv-update-reproducible-mac/bin/pip install -r requirements/base.txt
	venv-update-reproducible-mac/bin/pip-compile --generate-hashes --allow-unsafe -o requirements/reproducible-mac.txt

# note that this should be run on a windows environment with python3.8 as default interpreter
update-reproducible-win-reqs:
	python -m venv venv-update-reproducible-win
	.\venv-update-reproducible-win\Scripts\activate
	pip install --upgrade pip-tools pip
	pip install -r requirements\base.txt
	pip-compile --generate-hashes --allow-unsafe -o requirements\reproducible-win.txt


update-reproducible-reqs: update-reproducible-linux-reqs update-reproducible-mac-reqs