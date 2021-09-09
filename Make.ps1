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
    [Parameter(ParameterSetName = 'FnBlack')]
    [switch]
    $Black,

    # Perform format check
    [Parameter(ParameterSetName = 'FnBlackCheck')]
    [switch]
    $BlackCheck,

    # Command to run everytime you make changes to verify everything works
    [Parameter(ParameterSetName = 'FnDev')]
    [switch]
    $Dev,

    # Verify function test coverage only for `samcli.local` package
    [Parameter(ParameterSetName = 'FnFuncTest')]
    [switch]
    $FuncTest,

    # Install all dependencies
    [Parameter(ParameterSetName = 'FnInit')]
    [switch]
    $Init,

    # Run integration tests
    [Parameter(ParameterSetName = 'FnIntegTest')]
    [switch]
    $IntegTest,

    # Linter performs static analysis to catch latent bugs and mypy performs type check
    [Parameter(ParameterSetName = 'FnLint')]
    [switch]
    $Lint,

    # Verifications to run before sending a pull request
    [Parameter(ParameterSetName = 'FnPr')]
    [switch]
    $Pr,

    # Run regression tests
    [Parameter(ParameterSetName = 'FnRegresTest')]
    [switch]
    $RegresTest,

    # Smoke tests run in parallel
    [Parameter(ParameterSetName = 'FnSmokeTest')]
    [switch]
    $SmokeTest,

    # Run unit tests
    [Parameter(ParameterSetName = 'FnTest')]
    [switch]
    $Test,

    # Run unit tests with html coverage report
    [Parameter(ParameterSetName = 'FnTestCovReport')]
    [switch]
    $TestCovReport,

    # Update reproducable requirements.
    [Parameter(ParameterSetName = 'FnUpdateReproducibleReqs')]
    [switch]
    $UpdateReproducibleReqs
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
    echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional
}

function FnInit {
    pip install -e '.[dev]'
}

function FnIntegTest {
    # Integration tests don't need code coverage
    echo Telemetry Status: $[SAM_CLI_TELEMETRY]
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
    echo Telemetry Status: $[SAM_CLI_TELEMETRY]
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

        $Black {
            FnBlack
        }
        $BlackCheck {
            FnBlackCheck
        }
        $Dev {
            FnDev
        }
        $FuncTest {
            FnFuncTest
        }
        $Init {
            FnInit
        }
        $IntegTest {
            FnIntegTest
        }
        $Lint {
            FnLint
        }
        $Pr {
            FnPr
        }
        $RegresTest {
            FnRegresTest
        }
        $SmokeTest {
            FnSmokeTest
        }
        $Test {
            FnTest
        }
        $TestCovReport {
            FnTestCovReport
        }
        $UpdateReproducibleReqs {
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
