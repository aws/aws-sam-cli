#!/bin/bash

# ensure the script works regardless of where it's invoked from
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# set up virtual environment
python3 -m venv ./venv
source venv/bin/activate

# install dependencies
pip install -r requirements.txt

# execute hook with any arguments passed in
python hook.py "$@"