Import-Module -Name Pester

Describe "HelloWorld Tests" {

    $srcRoot = Join-Path -Path $PSScriptRoot -ChildPath "../src" -Resolve

    Mock -CommandName "Write-Host" -MockWith {}

    It "Should write the input to the host stream" {
        $functionPath = Join-Path -Path $srcRoot -ChildPath "Function.ps1"
        $result = . $functionPath
        Assert-MockCalled -CommandName Write-Host -Times 1
        $result.message | Should Be "hello world"
    }
}
