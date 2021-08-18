<#
.SYNOPSIS
    Run on Windows the same commands as in ./Makefile without installing any aditional software.

.DESCRIPTION
    Run on Windows the same commands as in ./Makefile without installing any aditional software.
    The only difference is syntax. Instead of make commands use parameters, meaning add '-' before the command.
    Parameter names are case insensetive.
    See Examples.

.EXAMPLE
    ./Make -TestCovReport

.EXAMPLE
    ./Make -pr
#>
[CmdletBinding(DefaultParameterSetName = '_')] # ParameterSetName '_'is just a workaround to redirect to default case
param (
    # Install all dependencies
    [Parameter(ParameterSetName = 'Init')]
    [switch]
    $Init,

    # Run unit tests and fail if coverage falls below 95%
    [Parameter(ParameterSetName = 'Test')]
    [switch]
    $Test,

    # Run unit tests with html coverage report
    [Parameter(ParameterSetName = 'TestCovReport')]
    [switch]
    $TestCovReport,

    # Run integration tests; they don't need code coverage
    [Parameter(ParameterSetName = 'IntegTest')]
    [switch]
    $IntegTest,

    # Verify function test coverage only for `samcli.local` package
    [Parameter(ParameterSetName = 'FuncTest')]
    [switch]
    $FuncTest,

    # Run regression tests
    [Parameter(ParameterSetName = 'RegresTest')]
    [switch]
    $RegresTest,

    # Smoke tests run in parallel
    [Parameter(ParameterSetName = 'SmokeTest')]
    [switch]
    $SmokeTest,

    # Linter performs static analysis to catch latent bugs and mypy performs type check
    [Parameter(ParameterSetName = 'Lint')]
    [switch]
    $Lint,
    
    # Lint and then test
    [Parameter(ParameterSetName = 'Dev')]
    [switch]
    $Dev,

    # Format with black
    [Parameter(ParameterSetName = 'Black')]
    [switch]
    $Black,

    # Perform format check
    [Parameter(ParameterSetName = 'BlackCheck')]
    [switch]
    $BlackCheck,

    # install, lint, check formating
    [Parameter(ParameterSetName = 'Pr')]
    [switch]
    $Pr

    # Update reproducable requirements. Path to python interpreter
    # [Parameter(ParameterSetName = 'UpdReq')]
    # [string]
    # $UpdateReproducableReqs
)

function Init {
    pip install -e '.[dev]'
}

function Test {
    pytest --cov samcli --cov-report term-missing --cov-fail-under 95 tests/unit
}

function Lint {
    pylint --rcfile .pylintrc samcli
    mypy setup.py samcli tests
}

function Dev {
    Lint
    Test
}

function BlackCheck {
    black --check setup.py samcli tests
}

if ( -not (Test-Path "env:SAM_CLI_TELEMETRY")) {
    $env:SAM_CLI_TELEMETRY = 0
}

$env:SAM_CLI_DEV = 1

try {
    switch ($true) {
        $Init { 
            Init
        }
        $Test {
            Test
        }
        $TestCovReport {
            pytest --cov samcli --cov-report html --cov-fail-under 95 tests/unit
        }
        $IntegTest {
            Write-Host "Telemetry Status: $env:SAM_CLI_TELEMETRY"
	        pytest tests/integration
        }
        $FuncTest {
            Write-Host "Telemetry Status: $env:SAM_CLI_TELEMETRY"
	        pytest --cov samcli.local --cov samcli.commands.local --cov-report term-missing tests/functional
        }
        $RegresTest {
            Write-Host "Telemetry Status: $env:SAM_CLI_TELEMETRY"
	        pytest tests/regression
        }
        $SmokeTest {
            Write-Host "Telemetry Status: $env:SAM_CLI_TELEMETRY"
	        pytest -n 4 tests/smoke
        }
        $Lint {
            Lint
        }
        $Dev {
            Dev
        }
        $Black {
            black setup.py samcli tests
        }
        $BlackCheck {
            BlackCheck
        }
        $Pr {
            Init
            Dev
            BlackCheck
        }
        
        default { Write-Host 'You have to specify one of the parameters. Call Get-Help ./Make.ps1 for more information' -ForegroundColor red }
    }
}
finally {
    $env:SAM_CLI_DEV = ''
}
