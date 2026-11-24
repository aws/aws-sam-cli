# AGENTS.md

Guidance for coding agents working in the AWS SAM CLI repository (`aws-sam-cli`, the `sam` command).
Human-oriented docs: `DEVELOPMENT_GUIDE.md`, `CONTRIBUTING.md`, `DESIGN.md`.

## Project overview

- Python CLI (Click) for building, locally emulating, and deploying serverless apps defined in SAM/CloudFormation
  templates (also CDK synth output and Terraform via hooks).
- Python `>=3.10`. Do not use language features newer than 3.10.
- Version lives in `samcli/__init__.py` (`__version__`). Do not bump it unless asked.
- Default branch is `develop`; PRs target `develop`.

## Setup

```sh
python3 -m venv .venv && source .venv/bin/activate
make init          # pip install -e '.[dev]' with SAM_CLI_DEV=1; puts `samdev` on PATH
samdev --version   # dev build of the CLI (use instead of `sam` to exercise local changes)
```

Windows: `./Make.ps1 -Init` (and `-pr`, `-Black`, etc.).

## Commands to verify changes

| Task | Command |
|---|---|
| Format | `make black` (black, line length 120) |
| Format check | `make black-check` |
| Lint + types | `make lint` (`ruff check samcli schema` + `mypy ... setup.py samcli tests schema`) |
| Unit tests (default) | `make test` (excludes `tests/unit/lib/cfn_language_extensions`, coverage gate 94%) |
| All unit tests | `make test-all` |
| Lint + tests | `make dev` (auto-selects `test-all` if `cfn_language_extensions/` changed) |
| Full PR check | `make pr` (init, schema, black-check, lint, test-all) |
| Regenerate samconfig schema | `make schema` |
| Single test | `pytest tests/unit/path/to/test_file.py -k test_name` |

For fast iteration, run only the relevant unit tests with `pytest`, then `make black` and `make lint` before
finishing. The coverage gate only applies to full-suite runs.

Integration (`tests/integration`), regression, smoke, and end-to-end tests need Docker (or Finch) and often real
AWS credentials, and they create real cloud resources. **Do not run them unless the user asks.** Functional tests
(`make func-test`) need Docker.

## Repository layout

```
samcli/
  cli/            Click framework: root command, lazy loading, config-file (samconfig) option handling,
                  global config, help formatting (cli/core/, row_modifiers.py, formatters.py)
  commands/       One package per `sam` command (init, validate, build, local, package, deploy, delete,
                  logs, publish, traces, sync, pipeline, list, docs, remote). Thin Click layer only.
    _utils/       Shared options (options.py), custom option types, exception handler, CDK decorators
  lib/            Business logic, UI-agnostic (no Click). e.g. build/, deploy/, package/, sync/,
                  providers/ (template -> functions/APIs/layers/stacks), intrinsic_resolver/,
                  cfn_language_extensions/, translate/, telemetry/, config/ (samconfig), utils/
  local/          Local emulation: docker/ (container mgmt, Docker/Finch clients, Lambda images),
                  apigw/ (Flask-based API Gateway emulator), lambda_service/, lambdafn/, layers/,
                  rapid/ (Lambda runtime interface emulator), events/
  hook_packages/  IaC hooks (terraform/) for `--hook-name`
  vendor/         Vendored serverlessrepo code
  runtime_config.json  Pinned commit of the app-templates repo used by `sam init` (bot-updated)
schema/           make_schema.py generates schema/samcli.json (samconfig JSON schema) from Click options
tests/
  unit/           Mirrors samcli/ layout (note: tests/unit/commands/buildcmd for commands/build)
  functional/     Uses real deps (Docker, filesystem); mocks AWS
  integration/    Customer-facing behavior; real AWS + containers; testdata/ holds fixture projects
  regression/, smoke/, end_to_end/
designs/          Feature design docs (_template.md)
installer/        PyInstaller and native installer builds
requirements/     Auto-generated reproducible-*.txt lockfiles + pyinstaller-build.txt
```

## Architecture conventions

- **Command registration**: each command package exposes a Click object named `cli`; the last module name is the
  command name. Top-level commands are listed in `_SAM_CLI_COMMAND_PACKAGES` (`samcli/cli/command.py`) and their
  short help in `SAM_CLI_COMMANDS` (`samcli/cli/root/command_list.py`); keep both in sync when adding one.
- **`cli` vs `do_cli`**: the Click-decorated `cli(...)` only forwards to `do_cli(...)`, which holds the logic and is
  what unit tests call. Heavy imports are deferred inside `do_cli` to keep CLI startup fast; keep that pattern.
- **Standard decorator stack** on commands (see `samcli/commands/validate/validate.py`): `configuration_option`,
  command options, `aws_creds_options`, `common_options`, `save_params_option`, `pass_context`, `track_command`,
  `check_newer_version`, `print_cmdline_args`, `command_exception_handler`.
- **Help option grouping**: each command has `core/command.py` (custom Click command class) and `core/options.py`
  listing option names in display groups. **A new option must be added to the right list in `core/options.py`**,
  or it won't appear in grouped help (unit tests check this).
- **samconfig schema**: adding, removing, or changing a command option or its help text changes
  `schema/samcli.json`. Run `make schema` and commit the result; CI fails if it is stale.
- **Layering**: `samcli/lib` and `samcli/local` must not import Click. Click usage stays in `samcli/commands` and
  `samcli/cli`. Library code exposes UI-independent interfaces.
- **Template access**: use the providers in `samcli/lib/providers/` (`SamFunctionProvider`, `SamApiProvider`,
  `SamLayerProvider`, `SamLocalStackProvider`) rather than parsing template dicts ad hoc. They handle nested
  stacks, intrinsics, and CDK metadata.

## Code style

- black + ruff, line length 120. Ruff rules: E, F, PL (pylint), I (isort), TID. **Relative imports are banned**;
  always use absolute imports (`from samcli.lib...`).
- Ruff pylint limits: max 25 branches, 8 returns, 80 statements per function. Split functions rather than adding
  `noqa`.
- Add type hints to all new functions and methods (required by the PR checklist; mypy runs over `samcli` and
  `tests`).
- Docstrings use numpy format. Update old-style docstrings on methods you modify.
- Module logger: `LOG = logging.getLogger(__name__)`.
- No logic in `__init__.py` files (command packages may re-export `cli`).
- Errors:
  - Raise custom exceptions, not bare built-ins (`KeyError`, `TypeError`, ...).
  - User-facing command errors must subclass `click.ClickException`, usually `samcli.commands.exceptions.UserException`.
    Pass `wrapped_from=` when wrapping another exception.
  - Each package keeps its own `exceptions.py`.
- Don't catch broad `Exception` without a comment explaining why. Avoid `*args`/`**kwargs` without strong
  justification.
- Integration tests must be region-agnostic: use the boto3 session region or `${AWS::Region}`, never hardcode a
  region.

## Testing conventions

- Unit tests use `unittest.TestCase`, `unittest.mock` (`patch`, `Mock`), and `parameterized`, run by pytest.
  Patch at the import location used by the module under test (e.g. `@patch("samcli.commands.validate.validate.click")`).
- Put tests at the mirrored path under `tests/unit/`. Cover new and changed branches. Don't duplicate existing tests
  or test third-party libraries (see the AI usage section of `CONTRIBUTING.md`).
- `pytest.ini` sets `filterwarnings = error`, so **new warnings fail tests**. Fix the cause rather than adding broad
  ignores.
- Telemetry is disabled in tests (`tests/conftest.py`, `SAM_CLI_TELEMETRY=0` in the Makefile).
- Integration markers (`pytest.ini`):
  - `requires_credential`
  - `tier1` / `tier1_extra` (cross-platform smoke subset)
  - `pr_skip`
  - `flaky`
  - runtime markers (`python`, `nodejs`, `java`, ...)

  See `CONTRIBUTING.md` for when to use each, and follow the Docker container snapshot/cleanup pattern in
  `start_api_integ_base.py` and `start_lambda_api_integ_base.py`.

## Common change recipes

- **New Lambda runtime** (see commit `02a9ec3ab`, "add Python 3.15 runtime", for a full example):
  - `samcli/lib/build/workflow_config.py`
  - `samcli/lib/utils/architecture.py`
  - `samcli/local/common/runtime_template.py`
  - `samcli/local/docker/lambda_debug_settings.py`
  - `samcli/local/docker/lambda_image.py`
  - runtime help text in `samcli/commands/build/command.py`, then `make schema`
  - unit tests (workflow_config, lambda container/debug settings, init CLI) and integration testdata
- **New command option**: add it to the command, add it to the command's `core/options.py` group, run
  `make schema`, and add unit tests for `do_cli` and the option.
- **Dependency change**:
  - Edit `pyproject.toml`: runtime deps go in `[project].dependencies`, dev deps in `[project.optional-dependencies].dev`.
  - Run `make update-reproducible-reqs` (needs `uv`). Never hand-edit `requirements/reproducible-*.txt`.
  - For runtime deps, also update `installer/assets/THIRD-PARTY-LICENSES`.
- **Feature-sized change**: you may need a design doc in `designs/` (see "Design Document" in `DEVELOPMENT_GUIDE.md`).

## Don'ts

- Don't edit generated files by hand: `schema/samcli.json` (use `make schema`), `requirements/reproducible-*.txt`.
- Don't format or lint excluded fixture trees (`samcli/lib/init/templates`, `tests/integration/testdata`) or
  reformat unrelated code. Keep diffs focused.
- Don't run integration tests or anything that deploys to AWS without explicit user approval.
- Don't change `runtime_config.json` or `__version__` unless asked (both are managed by release automation).

## Commits and PRs

- Conventional-commit style subjects: `feat:`, `fix:`, `fix(scope):`, `chore:`, `chore(deps):`, `test:`, `docs:`.
- Fill in `.github/PULL_REQUEST_TEMPLATE.md`, and make sure `make pr` passes. Keep PR descriptions concise.
