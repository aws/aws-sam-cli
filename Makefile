init:
	SAM_CLI_DEV=1 pip install -e .
	SAM_CLI_DEV=1 pip install -r requirements/dev.txt

test:
	# Run unit tests
	# Fail if coverage falls below 95%
	pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit

integ-test:
	# Integration tests don't need code coverage
	SAM_CLI_DEV=1 pytest tests/integration

func-test:
	# Verify function test coverage only for `samcli.local` package
	pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional

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
