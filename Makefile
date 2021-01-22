# Default value for environment variable. Can be overridden by setting the
# environment variable.
SAM_CLI_TELEMETRY ?= 0

init:
	SAM_CLI_DEV=1 pip install -e '.[dev]'

test:
	# Run unit tests
	# Fail if coverage falls below 95%
	pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit

test-cov-report:
	# Run unit tests with html coverage report
	pytest --cov samcli --cov-report html --cov-fail-under 95 tests/unit

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
	pylint --rcfile .pylintrc samcli
	# mypy performs type check
	mypy setup.py samcli tests

# Command to run everytime you make changes to verify everything works
dev: lint test

black:
	black setup.py samcli tests

black-check:
	black --check setup.py samcli tests

# Verifications to run before sending a pull request
pr: init dev black-check

update-reproducible-reqs:
	python3.7 -m venv venv-update-reproducible-requirements
	venv-update-reproducible-requirements/bin/pip install --upgrade pip-tools pip
	venv-update-reproducible-requirements/bin/pip install -r requirements/base.txt
	venv-update-reproducible-requirements/bin/pip-compile --generate-hashes --allow-unsafe -o requirements/reproducible-linux.txt
