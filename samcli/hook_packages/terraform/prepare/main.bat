@echo off&setlocal
:: redirect all stdout except for hook output to stderr
(
    :: ensure the script works regardless of where it's invoked from
    for %%i in ("%~dp0.") do set "parent_path=%%~fi"
    cd %parent_path%

    :: check that python 3 is installed
    py -3 --version >NUL 2>&1
    if errorlevel 1 goto errorNoPython

    :: set up virtual environment
    py -3 -m venv ./venv
    CALL venv/Scripts/activate

    :: install dependencies
    pip install -r requirements.txt

    :: execute hook if setup was successful
    goto:hook
)>&2

:errorNoPython
echo Python 3 not found. Please install before proceeding. >&2
exit /b 1

:: execute hook with any arguments passed in
:hook
python hook.py %*