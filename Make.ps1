<#
WARNING! Do not make changes in this file.

Changes should me made in Make.ps1.jinja and updatetargets.py

.SYNOPSIS
    Run on Windows the same commands as in ./Makefile without installing any aditional software.

.DESCRIPTION
    Run on Windows the same commands as in ./Makefile without installing any aditional software.
    The only difference is syntax. Instead of make commands use parameters, meaning add '-' before the command.
    Parameter names are case insensitive.
    See Examples.

.EXAMPLE
    ./Make -TestCovReport

.EXAMPLE
    ./Make -pr
#>
[CmdletBinding(DefaultParameterSetName = '_')] # ParameterSetName '_'is just a workaround to redirect to default case
param (


    # Format with black
    [Parameter(ParameterSetName = 'Black')]
    [switch]
    $FnBlack,

    # Perform format check
    [Parameter(ParameterSetName = 'BlackCheck')]
    [switch]
    $FnBlackCheck,

    # Command to run everytime you make changes to verify everything works
    [Parameter(ParameterSetName = 'Dev')]
    [switch]
    $FnDev,

    # Verify function test coverage only for `samcli.local` package
    [Parameter(ParameterSetName = 'FuncTest')]
    [switch]
    $FnFuncTest,

    # Install all dependencies
    [Parameter(ParameterSetName = 'Init')]
    [switch]
    $FnInit,

    # Run integration tests
    [Parameter(ParameterSetName = 'IntegTest')]
    [switch]
    $FnIntegTest,

    # Linter performs static analysis to catch latent bugs and mypy performs type check
    [Parameter(ParameterSetName = 'Lint')]
    [switch]
    $FnLint,

    # Verifications to run before sending a pull request
    [Parameter(ParameterSetName = 'Pr')]
    [switch]
    $FnPr,

    # Run regression tests
    [Parameter(ParameterSetName = 'RegresTest')]
    [switch]
    $FnRegresTest,

    # Smoke tests run in parallel
    [Parameter(ParameterSetName = 'SmokeTest')]
    [switch]
    $FnSmokeTest,

    # Run unit tests
    [Parameter(ParameterSetName = 'Test')]
    [switch]
    $FnTest,

    # Run unit tests with html coverage report
    [Parameter(ParameterSetName = 'TestCovReport')]
    [switch]
    $FnTestCovReport,

    # Update reproducable requirements.
    [Parameter(ParameterSetName = 'UpdateReproducibleReqs')]
    [switch]
    $FnUpdateReproducibleReqs
)


function FnBlack {
    black setup.py samcli tests
}

function FnBlackCheck {
    black --check setup.py samcli tests
}

function FnDev {
    FnLint
    FnTest
}

function FnFuncTest {
    # Verify function test coverage only for `samcli.local` package
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional
}

function FnInit {
    pip install -e '.[dev]'
}

function FnIntegTest {
    # Integration tests don't need code coverage
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest tests/integration
}

function FnLint {
    pylint --rcfile .pylintrc samcli
    mypy setup.py samcli tests
}

function FnPr {
    FnInit
    FnDev
    FnBlackCheck
}

function FnRegresTest {
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest tests/regression
}

function FnSmokeTest {
    # Smoke tests run in parallel
    pytest -n 4 tests/smoke
}

function FnTest {
    # Fail if coverage falls below 95%
    pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit
}

function FnTestCovReport {
    pytest --cov samcli --cov-report html --cov-fail-under 95 tests/unit
}

function FnUpdateReproducibleReqs {
    python3.7 -m venv venv-update-reproducible-requirements
    venv-update-reproducible-requirements/bin/pip install --upgrade pip-tools pip
    venv-update-reproducible-requirements/bin/pip install -r requirements/base.txt
    venv-update-reproducible-requirements/bin/pip-compile --generate-hashes --allow-unsafe -o requirements/reproducible-linux.txt
}


if ( -not (Test-Path "env:SAM_CLI_TELEMETRY")) {
    $env:SAM_CLI_TELEMETRY = 0
}

$env:SAM_CLI_DEV = 1

try {
    switch ($true) {

        Fn$Black {
            FnBlack
        }
        Fn$BlackCheck {
            FnBlackCheck
        }
        Fn$Dev {
            FnDev
        }
        Fn$FuncTest {
            FnFuncTest
        }
        Fn$Init {
            FnInit
        }
        Fn$IntegTest {
            FnIntegTest
        }
        Fn$Lint {
            FnLint
        }
        Fn$Pr {
            FnPr
        }
        Fn$RegresTest {
            FnRegresTest
        }
        Fn$SmokeTest {
            FnSmokeTest
        }
        Fn$Test {
            FnTest
        }
        Fn$TestCovReport {
            FnTestCovReport
        }
        Fn$UpdateReproducibleReqs {
            FnUpdateReproducibleReqs
        }
        default {
            Get-Help ./Make
        }
    }
}
finally {
    $env:SAM_CLI_DEV = ''
}
