# AWS SAM CLI Development Guide

**Welcome hacker!**

This document will make your life easier by helping you setup a
development environment, IDEs, tests, coding practices, or anything that
will help you be more productive. If you found something is missing or
inaccurate, update this guide and send a Pull Request.

## 1-Click Ready to Hack IDE (this section might be outdated, to be verified)

For setting up a local development environment, we recommend using Gitpod - a service that allows you to spin up an in-browser Visual Studio Code-compatible editor, with everything set up and ready to go for development on this project. Just click the button below to create your private workspace:

[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/aws/aws-sam-cli)

This will start a new Gitpod workspace, and immediately kick off a build of the code. Once it's done, you can start working.

Gitpod is free for 50 hours per month - make sure to stop your workspace when you're done (you can always resume it later, and it won't need to run the build again).

## Environment Setup
### 1. Prerequisites (Python Virtual Environment)

AWS SAM CLI is mainly written in Python 3 and we support Python 3.8 and above.
So, having a Python environment with this version is required.

Having a dedicated Python virtual environment ensures it won't "pollute" or get "polluted" 
by other python packages. Here we introduce two ways of setting up a Python virtual environment:
(1) Python's built in [`venv`](https://docs.python.org/3/tutorial/venv.html) and (2) [`pyenv`](https://github.com/pyenv/pyenv).

**Note**: `pyenv` currently only supports macOS and Linux. If you are a
Windows users, consider using [pyenv-win](https://github.com/pyenv-win/pyenv-win).

|    | `venv`   | `pyenv`      |
| -- | -------- | ------------ |
| Pick if you want ... | Easy setup | You want to develop and test SAM CLI in different Python versions |


#### `venv` setup

```sh
python3 -m venv .venv  # one time setup: create a virtual environment to directory .venv
source .venv/bin/activate  # activate the virtual environment
```
#### `pyenv` setup

Install `pyenv` and [`pyenv-virtualenv` plugin](https://github.com/pyenv/pyenv-virtualenv)

On macOS with [Homebrew](https://brew.sh/)

```sh
brew install pyenv
brew install pyenv-virtualenv
```

or using [pyenv-installer](https://github.com/pyenv/pyenv-installer) and git

```sh
curl https://pyenv.run | bash  # https://github.com/pyenv/pyenv-installer
exec $SHELL  # restart your shell so the path changes take effect
git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv
exec $SHELL  # restart your shell to enable pyenv-virtualenv
```

Next, setup a virtual environment and activate it:

```sh
# Assuming you want to develop AWS SAM CLI in Python 3.8.9
pyenv install 3.8.9  # install Python 3.8.9 using pyenv
pyenv virtualenv 3.8.9 samcli38  # create a virtual environment using 3.8.9 named "samcli38"
pyenv activate samcli38  # activate the virtual environment
```

### 2. Initialize dependencies and create `samdev` available in `$PATH`

Clone the AWS SAM CLI repository to your local machine if you haven't done that yet.

```sh
# Using SSH
git clone git@github.com:aws/aws-sam-cli.git
```
or
```sh
# Using HTTPS
git clone https://github.com/aws/aws-sam-cli.git
```

(make sure you have virtual environment activated)

```sh
cd aws-sam-cli
make init  # this will put a file `samdev` available in $PATH
```
Windows users can use PowerShell and `Make.ps1` script which performs the tasks from `Makefile` without *nix `make` tool.

```PowerShell
cd aws-sam-cli
./Make -Init
```

Now you can verify whether the dev AWS SAM CLI is available:

```sh
samdev --version  # this will print something like "SAM CLI, version x.xx.x"
```

#### Try out to make change to AWS SAM CLI (Optional)

```sh
# Change the AWS SAM CLI version to 123.456.789
echo '__version__ = "123.456.789"' >> samcli/__init__.py
samdev --version  # this will print "SAM CLI, version 123.456.789"
```

### 3. (Optional) Install development version of SAM Transformer

If you want to run the latest version of [SAM Transformer](https://github.com/aws/serverless-application-model/)
or work on it at the same time, you can clone it locally and install it in your virtual environment. 
This is useful if you want to validate your templates against any new, unreleased SAM features ahead of time.


```sh
# Make sure it is not in AWS SAM CLI repository

# clone the AWS SAM repo
git clone git@github.com:aws/serverless-application-model.git
# or using HTTPS: git clone https://github.com/aws/serverless-application-model.git

cd serverless-application-model
```

Make sure you are in the same virtual environment as the one you are using with SAM CLI.
```sh
source <sam-cli-directory-path>/.venv/bin/activate  # if you chose to use venv to setup the virtual environment
# or
pyenv activate samcli38  # if you chose to use pyenv to setup the virtual environment
```

Install the SAM Transformer in editable mode so that 
all changes you make to the SAM Transformer locally are immediately picked up for SAM CLI. 

```sh
pip install -e .
```

Move back to your SAM CLI directory and re-run init, If necessary: open requirements/base.txt and replace the version number of aws-sam-translator with the ``version number`` specified in your local version of `serverless-application-model/samtranslator/__init__.py`

```sh
# Make sure you are back to your SAM CLI directory
make init
```

Or on Windows

```PowerShell
./Make -Init
```

## Making a Pull Request

Above demonstrates how to setup the environment, which is enough
to play with the AWS SAM CLI source code. However, if you want to
contribute to the repository, there are a few more things to consider.

### Make Sure AWS SAM CLI Work in Multiple Python Versions

We support version 3.8 and above. Our CI/CD pipeline is setup to run
unit tests against all Python versions. So make sure you test it
with all versions before sending a Pull Request.
See [Unit testing with multiple Python versions](#unit-testing-with-multiple-python-versions-optional). 
This is most important if you are developing in a Python version greater than the minimum supported version (currently 3.8), as any new features released in 3.9+ will not work.

If you chose to use `pyenv` in the previous session, setting up a 
different Python version should be easy:

(assuming you are in virtual environment named `samcli39` with Python version 3.9.x)

```sh
# Your shell now should look like "(samcli39) $"
pyenv deactivate samcli39  # "(samcli39)" will disappear
pyenv install 3.8.9  # one time setup
pyenv virtualenv 3.8.9 samcli38  # one time setup
pyenv activate samcli38
# Your shell now should look like "(samcli38) $"

# You can verify the version of Python
python --version  # Python 3.8.9

make init  # one time setup, this will put a file `samdev` available in $PATH
```

For Windows, use your favorite tool for managing different python versions and environments and call `./Make -Init` to initialize each of the environments.

### Format Python Code

We format our code using [Black](https://github.com/python/black) and verify the source code is
black compliant in AppVeyor during PRs. Black will be installed automatically with `make init` or `./Make -Init` on Windows.

There are generally 3 options to make sure your change is compliant with our formatting standard:

#### (Option 1) Run `make black`

```sh
make black
```

On Windows:

```PowerShell
./Make -Black
```

#### (Option 2) Integrating Black directly in your favorite IDE

Since black is installed in virtualenv, when you follow [this instruction](https://black.readthedocs.io/en/stable/editor_integration.html), `which black` might give you this

```
/Users/<username>/.pyenv/shims/black
```

However, IDEs such PyChaim (using FileWatcher) will have a hard time 
invoking `/Users/<username>/.pyenv/shims/black` 
and this will happen:

```
pyenv: black: command not found

The `black' command exists in these Python versions:
  3.8.9/envs/samcli38
  samcli38
``` 

A simple workaround is to use `/Users/<username>/.pyenv/versions/samcli37/bin/black` 
instead of `/Users/<username>/.pyenv/shims/black`.

#### (Option 3) Pre-commit

We have integrated black into git hooks through [pre-commit](https://pre-commit.com/).
After installing pre-commit, run `pre-commit install` in the root of the project. This will install black for you and run the black formatting on commit.

### Do a Local PR Check

This commands will run the AWS SAM CLI code through various checks including
lint, formatter, unit tests, function tests, and so on.
```sh
make pr
```

Use `Make.ps1` script on Windows instead:

```PowerShell
./Make -pr
```

We also suggest to run `make pr` or `./Make -pr` in all Python versions.

#### Unit Testing with Multiple Python Versions (Optional)

Currently, SAM CLI only supports Python3 versions (see setup.py for exact versions). For the most
part, code that works in Python3.8 will work in Python3.9. You only run into problems if you are
trying to use features released in a higher version (for example features introduced into Python3.9
will not work in Python3.8). If you want to test in many versions, you can create a virtualenv for
each version and flip between them (sourcing the activate script). Typically, we run all tests in
one python version locally and then have our ci (appveyor) run all supported versions.

#### Integration Test (Optional)

`make integ-test` - To run integration test against global SAM CLI
installation. It looks for a command named `sam` in your shell.

`SAM_CLI_DEV=1 make integ-test` - To run integration tests against
development version of SAM CLI. This is useful if you are making changes
to the CLI and want to verify that it works. It is a good practice to
run integration tests before submitting a pull request.

On Windows, the behaviour is slightly different. `./Make -IntegTest` runs integration tests **only** against **development** version of SAM CLI.

`Make.ps1` script always sets environment to `dev` before running any command and resets `SAM_CLI_DEV` when done, even if a command fails.

```PowerShell
$env:SAM_CLI_DEV = 1
try {
  # execute commands here
  ...
}
finally {
  $env:SAM_CLI_DEV = ''
}
```

When writing integration tests, please don't hardcode region information assuming the tests will always run in that region. Please write integration tests region agnostic so that they will succeed when they are run in different regions. Use current region from `boto3` session or use ${AWS::Region} in the templates.

## Other Topics
### Code Conventions

Please follow these code conventions when making your changes. This will
align your code to the same conventions used in rest of the package and
make it easier for others to read/understand your code. Some of these
conventions are best practices that we have learnt over time.

-   Use [numpy
    docstring](https://numpydoc.readthedocs.io/en/latest/format.html)
    format for docstrings. Some parts of the code still use an older,
    unsupported format. If you happened to be modifying these methods,
    please change the docstring format as well.
-   Don\'t write any code in `__init__.py` file
-   Module-level logger variable must be named as `LOG`
-   If your method wants to report a failure, it *must* raise a custom
    exception. Built-in Python exceptions like `TypeError`, `KeyError`
    are raised by Python interpreter and usually signify a bug in your
    code. Your method must not explicitly raise these exceptions because
    the caller has no way of knowing whether it came from a bug or not.
    Custom exceptions convey are must better at conveying the intent and
    can be handled appropriately by the caller. In HTTP lingo, custom
    exceptions are equivalent to 4xx (user\'s fault) and built-in
    exceptions are equivalent to 5xx (Service Fault)
-   CLI commands must always raise a subclass of `click.ClickException`
    to signify an error. Error code and message must be set as a part of
    this exception and not explicitly returned by the CLI command.
-   Don't use `*args` or `**kwargs` unless there is a really strong
    reason to do so. You must explain the reason in great detail in
    docstrings if you were to use them.
-   Library classes, ie. the ones under `lib` folder, must **not** use
    Click. Usage of Click must be restricted to the `commands` package.
    In the library package, your classes must expose interfaces that are
    independent of the user interface, be it a CLI thru Click, or CLI
    thru argparse, or HTTP API, or a GUI.
-   Do not catch the broader `Exception`, unless you have a really
    strong reason to do. You must explain the reason in great detail in
    comments.
    
    
### Dependency Updates

Please update all the required files if the changes involve a version update on a dependency or to include a new dependency. The requirements files are located inside the `requirements` folder.

#### base.txt for SAM CLI code dependencies
For dependencies used in SAM CLI code, update `base.txt` in `requirements` folder. To update `base.txt` file, simply follow the current convention and input the dependency name plus version, together with any necessary comment. For more information on the operators to be used for restricting compatible versions, read on [python's enhancement proposals](https://peps.python.org/pep-0440/#compatible-release).

#### reproducible-linux.txt for SAM CLI code dependencies
For dependencies used in SAM CLI code, also remember to update`reproducible-linux.txt` in `requirements` folder and `THIRD-PARTY-LICENSES` in `installer/assets` folder. To update the `reproducible-linux.txt`, run the following script to replace the file:
```
make update-reproducible-reqs
```
Note that this is a fully auto-generated file, any manual changes to reproducible-linux.txt will not last after the next update running the above script. As for updating the `THIRD-PARTY-LICENSES`, find the corresponding dependency entry in the license file (usually grouped by licensing organization) and update the versions. For adding a new dependency, look up for its licensing organization through PyPi and update the corresponding section. If the license is from GNU or another license type not included in the file, please contact the repository maintainers first. If you are not familiar with working with this file, please contact one of the repository maintainers or cut an issue to help with the update.

#### dev.txt for SAM CLI test dependencies
For changing dependencies used for `make pr` checks and test related dependencies, update `dev.txt` in `requirements` folder only.

#### pyinstaller-build.txt for SAM CLI native installer build dependencies
For changing Python dependencies needed for creating builds through Pyinstaller (to run `build-mac.sh` or `build-linux.sh` in `installer/pyinstaller` folder), modify `pyinstaller-build.txt`.


### Our Testing Practices

We need thorough test coverage to ensure the code change works today, 
and continues to work in future. When you make a code change, use the 
following framework to decide the kinds of tests to write:

- When you adds/removed/modifies code paths (aka branches/arcs), 
  write **unit tests** with goal of making sure the flow works. Focus
  on verifying the flow and use mocks to isolate from as many 
  external dependencies as you can. "External dependencies" 
  includes system calls, libraries, other classes/methods you wrote
  but logically outside of the system-under-test.
  
  > Aim to test with complete isolation
  
- When your code uses external dependencies, write **functional tests** 
  to verify some flows by including as many external dependencies as 
  possible. Focus on verifying the flows that directly use the dependencies.
  
  > Aim to test one or more logically related components. Includes docker, 
  file system, API server, but might still mock some things like AWS API 
  calls. 
  
- When your code adds/removes/modifies a customer facing behavior,
  write **integration tests**. Focus on verifying the customer experience
  works as expected.
  
  > Aim to test how a customer will use the feature/command. Includes 
  calling AWS APIs, spinning up Docker containers, mutating files etc.
  

### Design Document

A design document is a written description of the feature/capability you
are building. We have a [design document
template](./designs/_template.md) to help you quickly fill in the
blanks and get you working quickly. We encourage you to write a design
document for any feature you write, but for some types of features we
definitely require a design document to proceed with implementation.

**When do you need a design document?**

-   Adding a new command
-   Making a breaking change to CLI interface
-   Refactoring code that alters the design of certain components
-   Experimental features
