# Default value for environment variable. Can be overridden by setting the
# environment variable.
SAM_CLI_TELEMETRY ?= 0

init:
	SAM_CLI_DEV=1 pip install -e '.[dev]'

test:
	# Run unit tests
	# Fail if coverage falls below 95%
	pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit

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

# Command to run everytime you make changes to verify everything works
dev: lint test

black:
	black samcli/* tests/* scripts/*

black-check:
	black --check samcli/* tests/* scripts/*

# Verifications to run before sending a pull request
pr: init dev black-check

update-isolated-req:
	pipenv --three
	pipenv run pip install -r requirements/base.txt
	pipenv run pip freeze > requirements/isolated.txt
