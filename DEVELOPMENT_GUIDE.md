DEVELOPMENT GUIDE
=================

**Welcome hacker!**

This document will make your life easier by helping you setup a
development environment, IDEs, tests, coding practices, or anything that
will help you be more productive. If you found something is missing or
inaccurate, update this guide and send a Pull Request.

**Note**: `pyenv` currently only supports macOS and Linux. If you are a
Windows users, consider using [pipenv](https://docs.pipenv.org/).

1-Click Ready to Hack IDE
-------------------------
For setting up a local development environment, we recommend using Gitpod - a service that allows you to spin up an in-browser Visual Studio Code-compatible editor, with everything set up and ready to go for development on this project. Just click the button below to create your private workspace:

[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/awslabs/aws-sam-cli)

This will start a new Gitpod workspace, and immediately kick off a build of the code. Once it's done, you can start working.

Gitpod is free for 50 hours per month - make sure to stop your workspace when you're done (you can always resume it later, and it won't need to run the build again).

Environment Setup
-----------------

### 1. Install Python Versions

We support 3.6 and 3.7 versions. Our CI/CD pipeline is setup to run
unit tests against both Python versions. So make sure you test it
with both versions before sending a Pull Request.
See [Unit testing with multiple Python versions](#unit-testing-with-multiple-python-versions).

[pyenv](https://github.com/pyenv/pyenv) is a great tool to
easily setup multiple Python versions.

> Note: For Windows, type
> `export PATH="/c/Users/<user>/.pyenv/libexec:$PATH"` to add pyenv to
> your path.

1.  Install PyEnv -
    `curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash`
2.  `pyenv install 3.6.8`
3.  `pyenv install 3.7.2`
4.  Make Python versions available in the project:
    `pyenv local 3.6.8 3.7.2`

### 2. Install Additional Tooling
#### Black
We format our code using [Black](https://github.com/python/black) and verify the source code is black compliant
in Appveyor during PRs. Black will be installed automatically with `make init`.

After installing, you can run our formatting through our Makefile by `make black` or integrating Black directly in your favorite IDE (instructions
can be found [here](https://black.readthedocs.io/en/stable/editor_integration.html))
 
##### (workaround) Integrating Black directly in your favorite IDE
Since black is installed in virtualenv, when you follow [this instruction](https://black.readthedocs.io/en/stable/editor_integration.html), `which black` might give you this

```bash
(samcli37) $ where black
/Users/<username>/.pyenv/shims/black
```

However, IDEs such PyChaim (using FileWatcher) will have a hard time invoking `/Users/<username>/.pyenv/shims/black` 
and this will happen:

```
pyenv: black: command not found

The `black' command exists in these Python versions:
  3.7.2/envs/samcli37
  samcli37
``` 

A simple workaround is to use `/Users/<username>/.pyenv/versions/samcli37/bin/black` 
instead of `/Users/<username>/.pyenv/shims/black`.

#### Pre-commit
If you don't wish to manually run black on each pr or install black manually, we have integrated black into git hooks through [pre-commit](https://pre-commit.com/).
After installing pre-commit, run `pre-commit install` in the root of the project. This will install black for you and run the black formatting on
commit.

### 3. Activate Virtualenv

Virtualenv allows you to install required libraries outside of the
Python installation. A good practice is to setup a different virtualenv
for each project. [pyenv](https://github.com/pyenv/pyenv) comes with a
handy plugin that can create virtualenv.

Depending on the python version, the following commands would change to
be the appropriate python version.

1.  `pyenv virtualenv 3.7.2 samcli37`
2.  `pyenv activate samcli37` for Python3.7

### 4. Install dev version of SAM CLI

We will install a development version of SAM CLI from source into the
virtualenv for you to try out the CLI as you make changes. We will
install in a command called `samdev` to keep it separate from a global
SAM CLI installation, if any.

1.  Activate Virtualenv: `pyenv activate samcli37`
2.  Install dev CLI: `make init`
3.  Make sure installation succeeded: `which samdev`

### 5. (Optional) Install development version of SAM Transformer

If you want to run the latest version of [SAM
Transformer](https://github.com/awslabs/serverless-application-model/),
you can clone it locally and install it in your pyenv. This is useful if
you want to validate your templates against any new, unreleased SAM
features ahead of time.

This step is optional and will use the specified version of
aws-sam-transformer from PyPi by default.


``cd ~/projects (cd into the directory where you usually place projects)``

``git clone https://github.com/awslabs/serverless-application-model/``

``git checkout develop ``

Install the SAM Transformer in editable mode so that all changes you make to the SAM Transformer locally are immediately picked up for SAM CLI. 

``pip install -e . `` 

Move back to your SAM CLI directory and re-run init, If necessary: open requirements/base.txt and replace the version number of aws-sam-translator with the ``version number`` specified in your local version of `serverless-application-model/samtranslator/__init__.py`

``cd ../aws-sam-cli``
 
``make init``

Running Tests
-------------

### Unit testing with one Python version

If you're trying to do a quick run, it's ok to use the current python version.  Run `make pr`.

### Unit testing with multiple Python versions

Currently, SAM CLI only supports Python3 versions (see setup.py for exact versions). For the most
part, code that works in Python3.6 will work in Python3.7. You only run into problems if you are
trying to use features released in a higher version (for example features introduced into Python3.7
will not work in Python3.6). If you want to test in many versions, you can create a virtualenv for
each version and flip between them (sourcing the activate script). Typically, we run all tests in
one python version locally and then have our ci (appveyor) run all supported versions.

### Integration Test

`make integ-test` - To run integration test against global SAM CLI
installation. It looks for a command named `sam` in your shell.

`SAM_CLI_DEV=1 make integ-test` - To run integration tests against
development version of SAM CLI. This is useful if you are making changes
to the CLI and want to verify that it works. It is a good practice to
run integration tests before submitting a pull request.

Code Conventions
----------------

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
    
    
Testing
-------

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
  

Design Document
---------------

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
