#!/bin/bash

# copy stdout to file descriptor 3, and redirect stdout to stderr
# this is to log everything to stderr (while maintaining a reference of stdout to restore later)
exec 3>&1 1>&2

# ensure the script works regardless of where it's invoked from
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# check that python 3 is installed
if ! $(command -v python3 >/dev/null 2>&1)
then
    echo Python 3 not found. Please install before proceeding.
    exit 1
fi

# set up virtual environment
python3 -m venv ./venv
source venv/bin/activate

# install dependencies
pip install -r requirements.txt

# copy file descriptor 3 back to stdout and close file descriptor 3
# this will ensure the output of the hook goes to stdout
exec 1>&3 3>&-
# execute hook with any arguments passed in
python hook.py "$@"