# Default value for environment variable. Can be overridden by setting the
# environment variable.
SAM_CLI_TELEMETRY ?= 0

.PHONY: schema init-nightly init-latest-release setup-pytest

# Initialize environment specifically for Github action tests using uv
init:
	@if [ "$$GITHUB_ACTIONS" = "true" ]; then \
		command -v uv >/dev/null 2>&1 || pip install uv==0.9.1; \
		SAM_CLI_DEV=1 uv pip install --system --break-system-packages --python $$UV_PYTHON -e '.[dev]'; \
	else \
		SAM_CLI_DEV=1 pip install -e '.[dev]'; \
	fi

# Set up a pytest venv with test dependencies (cross-platform)
setup-pytest:
	@if [ "$${RUNNER_OS:-}" = "Windows" ]; then \
	  python3.11 -m venv $(HOME)/pytest; \
	  VENV_PY="$(HOME)/pytest/Scripts/python.exe"; \
	  SAM_CLI_DEV=1 uv pip install --python "$$VENV_PY" -e '.[dev]'; \
	  "$(HOME)/pytest/Scripts/pytest" --version; \
	  if [ -n "$$GITHUB_ENV" ]; then \
	    echo "SCRIPT_PY=$$VENV_PY" >> "$$GITHUB_ENV"; \
	    echo "$(HOME)/pytest/Scripts" >> "$$GITHUB_PATH"; \
	  fi; \
	else \
	  python3.11 -m venv $(HOME)/pytest; \
	  VENV_PY="$(HOME)/pytest/bin/python3"; \
	  SAM_CLI_DEV=1 uv pip install --python "$$VENV_PY" -e '.[dev]'; \
	  sudo ln -sf $(HOME)/pytest/bin/pytest /usr/local/bin/pytest 2>/dev/null || true; \
	  $(HOME)/pytest/bin/pytest --version; \
	  if [ -n "$$GITHUB_ENV" ]; then \
	    echo "SCRIPT_PY=$$VENV_PY" >> "$$GITHUB_ENV"; \
	  fi; \
	fi
# Install SAM CLI nightly binary
init-nightly:
	bash tests/install-sam-cli-binary.sh sam-cli-nightly

# Install SAM CLI latest release binary
init-latest-release:
	bash tests/install-sam-cli-binary.sh

test:
	# Run unit tests and fail if coverage falls below 94%
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
	ruff check samcli schema
	# mypy performs type check
	mypy --exclude /testdata/ --exclude /init/templates/ --no-incremental setup.py samcli tests schema

# Command to run everytime you make changes to verify everything works
dev: lint test

black:
	black setup.py samcli tests schema

black-check:
	black --check setup.py samcli tests schema

format: black
	ruff check samcli --fix

schema:
	python -m schema.make_schema

# Verifications to run before sending a pull request
pr: init schema black-check dev

# Update all reproducible requirements using uv (can run from any platform)
update-reproducible-reqs:
	@command -v uv >/dev/null 2>&1 || pip install uv
	uv pip compile pyproject.toml --generate-hashes --output-file requirements/reproducible-linux.txt --python-platform linux --python-version 3.11 --no-cache --no-strip-extras
	uv pip compile pyproject.toml --generate-hashes --output-file requirements/reproducible-mac.txt --python-platform macos --python-version 3.11 --no-cache --no-strip-extras
	uv pip compile pyproject.toml --generate-hashes --output-file requirements/reproducible-win.txt --python-platform windows --python-version 3.12 --no-cache --no-strip-extras

# Alias for backwards compatibility
update-reproducible-reqs-uv: update-reproducible-reqs
