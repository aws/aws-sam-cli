:: ensure the script works regardless of where it's invoked from
@echo off&setlocal
for %%i in ("%~dp0.") do set "parent_path=%%~fi"
cd %parent_path%

:: set up virtual environment
python -m venv ./venv
CALL venv/Scripts/activate

:: install dependencies
pip install -r requirements.txt

:: execute hook with any arguments passed in
python hook.py %*