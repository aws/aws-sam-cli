Import-Module -Name AWSLambdaPSCore

$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath "Function.ps1"
New-AWSPowerShellLambdaPackage -ScriptPath $scriptPath -OutputPackage "{{ cookiecutter.project_name }}/artifacts/Function.zip"
