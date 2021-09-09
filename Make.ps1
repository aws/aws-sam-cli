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
    $Black,

    # Perform format check
    [Parameter(ParameterSetName = 'BlackCheck')]
    [switch]
    $BlackCheck,

    # Command to run everytime you make changes to verify everything works
    [Parameter(ParameterSetName = 'Dev')]
    [switch]
    $Dev,

    # Verify function test coverage only for `samcli.local` package
    [Parameter(ParameterSetName = 'FuncTest')]
    [switch]
    $FuncTest,

    # Install all dependencies
    [Parameter(ParameterSetName = 'Init')]
    [switch]
    $Init,

    # Run integration tests
    [Parameter(ParameterSetName = 'IntegTest')]
    [switch]
    $IntegTest,

    # Linter performs static analysis to catch latent bugs and mypy performs type check
    [Parameter(ParameterSetName = 'Lint')]
    [switch]
    $Lint,

    # Verifications to run before sending a pull request
    [Parameter(ParameterSetName = 'Pr')]
    [switch]
    $Pr,

    # Run regression tests
    [Parameter(ParameterSetName = 'RegresTest')]
    [switch]
    $RegresTest,

    # Smoke tests run in parallel
    [Parameter(ParameterSetName = 'SmokeTest')]
    [switch]
    $SmokeTest,

    # Run unit tests
    [Parameter(ParameterSetName = 'Test')]
    [switch]
    $Test,

    # Run unit tests with html coverage report
    [Parameter(ParameterSetName = 'TestCovReport')]
    [switch]
    $TestCovReport,

    # Update reproducable requirements.
    [Parameter(ParameterSetName = 'UpdateReproducibleReqs')]
    [switch]
    $UpdateReproducibleReqs
)


function Black {
    black setup.py samcli tests
}

function BlackCheck {
    black --check setup.py samcli tests
}

function Dev {
    Lint
    Test
}

function FuncTest {
    # Verify function test coverage only for `samcli.local` package
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional
}

function Init {
    pip install -e '.[dev]'
}

function IntegTest {
    # Integration tests don't need code coverage
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest tests/integration
}

function Lint {
    pylint --rcfile .pylintrc samcli
    mypy setup.py samcli tests
}

function Pr {
    Init
    Dev
    BlackCheck
}

function RegresTest {
    @echo Telemetry Status: $[SAM_CLI_TELEMETRY]
    pytest tests/regression
}

function SmokeTest {
    # Smoke tests run in parallel
    pytest -n 4 tests/smoke
}

function Test {
    # Fail if coverage falls below 95%
    pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit
}

function TestCovReport {
    pytest --cov samcli --cov-report html --cov-fail-under 95 tests/unit
}

function UpdateReproducibleReqs {
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
            Black
        }
        $BlackCheck {
            BlackCheck
        }
        $Dev {
            Dev
        }
        $FuncTest {
            FuncTest
        }
        $Init {
            Init
        }
        $IntegTest {
            IntegTest
        }
        $Lint {
            Lint
        }
        $Pr {
            Pr
        }
        $RegresTest {
            RegresTest
        }
        $SmokeTest {
            SmokeTest
        }
        $Test {
            Test
        }
        $TestCovReport {
            TestCovReport
        }
        $UpdateReproducibleReqs {
            UpdateReproducibleReqs
        }
        default {
            Get-Help ./Make
        }
    }
}
finally {
    $env:SAM_CLI_DEV = ''
}
