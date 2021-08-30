# WARNING! Do not make changes in this file.
#
# Changes should me made in Makefile.jinja and updatetargets.py
#

# Default value for environment variable. Can be overridden by setting the
# environment variable.
SAM_CLI_TELEMETRY ?= 0
SAM_CLI_DEV ?= 1


# Format with black
black:
	black setup.py samcli tests

# Perform format check
black-check:
	black --check setup.py samcli tests

# Command to run everytime you make changes to verify everything works
dev: lint test

# Verify function test coverage only for `samcli.local` package
func-test:
	# Verify function test coverage only for `samcli.local` package
	@echo Telemetry Status: $[SAM_CLI_TELEMETRY]
	pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional

# Install all dependencies
init:
	pip install -e '.[dev]'

# Run integration tests
integ-test:
	# Integration tests don't need code coverage
	@echo Telemetry Status: $[SAM_CLI_TELEMETRY]
	pytest tests/integration

# Linter performs static analysis to catch latent bugs and mypy performs type check
lint:
	pylint --rcfile .pylintrc samcli
	mypy setup.py samcli tests

# Verifications to run before sending a pull request
pr: init dev black-check

# Run regression tests
regres-test:
	@echo Telemetry Status: $[SAM_CLI_TELEMETRY]
	pytest tests/regression

# Smoke tests run in parallel
smoke-test:
	# Smoke tests run in parallel
	pytest -n 4 tests/smoke

# Run unit tests
test:
	# Fail if coverage falls below 95%
	pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit

# Run unit tests with html coverage report
test-cov-report:
	pytest --cov samcli --cov-report html --cov-fail-under 95 tests/unit

# Update reproducable requirements.
update-reproducible-reqs:
	python3.7 -m venv venv-update-reproducible-requirements
	venv-update-reproducible-requirements/bin/pip install --upgrade pip-tools pip
	venv-update-reproducible-requirements/bin/pip install -r requirements/base.txt
	venv-update-reproducible-requirements/bin/pip-compile --generate-hashes --allow-unsafe -o requirements/reproducible-linux.txt
