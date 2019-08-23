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

smoke-test:
	# Smoke tests run in parallel
	pytest -n 4 tests/functional

flake:
	# Make sure code conforms to PEP8 standards
	flake8 samcli
	flake8 tests/unit tests/integration

lint:
	# Linter performs static analysis to catch latent bugs
	pylint --rcfile .pylintrc samcli

# Command to run everytime you make changes to verify everything works
dev: flake lint test

# Verifications to run before sending a pull request
pr: init dev
