DEVELOPMENT GUIDE
=================

**Welcome hacker!**

This document will make your life easier by helping you setup a development environment, IDEs, tests, coding practices,
or anything that will help you be more productive. If you found something is missing or inaccurate, update this guide
and send a Pull Request.

**Note**: ``pyenv`` currently only supports macOS and Linux. If you are a Windows users, consider using `pipenv`_.

Environment Setup
-----------------

1. Install Python Versions
~~~~~~~~~~~~~~~~~~~~~~~~~~
We support Python 2.7, 3.6 and 3.7 versions.
Follow the idioms from this `excellent cheatsheet`_ to make sure your code is compatible with both Python versions.
Our CI/CD pipeline is setup to run unit tests against both Python versions. So make sure you test it with both
versions before sending a Pull Request. `pyenv`_ is a great tool to easily setup multiple Python versions.

    Note: For Windows, type ``export PATH="/c/Users/<user>/.pyenv/libexec:$PATH"`` to add pyenv to your path.

#. Install PyEnv - ``curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash``
#. ``pyenv install 2.7.14``
#. ``pyenv install 3.6.4``
#. ``pyenv install 3.7.0``
#. Make Python versions available in the project: ``pyenv local 3.6.4 2.7.14 3.7.0``


2. Activate Virtualenv
~~~~~~~~~~~~~~~~~~~~~~
Virtualenv allows you to install required libraries outside of the Python installation. A good practice is to setup
a different virtualenv for each project. `pyenv`_ comes with a handy plugin that can create virtualenv.

Depending on the python version, the following commands would change to be the appropriate python version.

#. ``pyenv virtualenv 3.7.0 samcli37``
#. ``pyenv activate samcli37`` for Python3.7


3. Install dev version of SAM CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
We will install a development version of SAM CLI from source into the virtualenv for you to try out the CLI as you
make changes. We will install in a command called ``samdev`` to keep it separate from a global SAM CLI installation,
if any.

#. Activate Virtualenv: ``pyenv activate samcli37``
#. Install dev CLI: ``make init``
#. Make sure installation succeeded: ``which samdev``

4. (Optional) Install development version of SAM Transformer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to run the latest version of [SAM Transformer](https://github.com/awslabs/serverless-application-model/), you can clone it locally and install it in your pyenv. This is useful if you want to validate your templates against any new, unreleased SAM features ahead of time.

This step is optional and will use the specified version of aws-sam-transformer from PyPi by default.

```bash
# cd into the directory where you usually place projects and clone the latest SAM Transformer
cd ~/projects
git clone https://github.com/awslabs/serverless-application-model/

# cd into the new directory and checkout the relevant branch
cd serverless-application-model
git checkout develop

# Install the SAM Transformer in editable mode so that all changes you make to
# the SAM Transformer locally are immediately picked up for SAM CLI.
pip install -e .

# Move back to your SAM CLI directory and re-run init
# If necessary: open requirements/base.txt and replace the version number of aws-sam-translator with the
# version number specified in your local version of serverless-application-model/samtranslator/__init__.py
cd ../aws-sam-cli
make init
```

Running Tests
-------------

Unit testing with multiple Python versions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`tox`_ is used to run tests against all supported Python versions. Follow these instructions to setup multiple Python
versions using `pyenv`_ before running tox:

#. Deactivate virtualenvs, if any: ``pyenv deactivate``
#. ``pip install tox``
#. Run tests against all supported Python versions: ``tox``

Integration Test
~~~~~~~~~~~~~~~~

``make integ-test`` - To run integration test against global SAM CLI installation. It looks for a command named ``sam``
in your shell.

``SAM_CLI_DEV=1 make integ-test`` - To run integration tests against development version of SAM CLI. This is useful if
you are making changes to the CLI and want to verify that it works. It is a good practice to run integration tests
before submitting a pull request.

Code Conventions
----------------

Please follow these code conventions when making your changes. This will align your code to the same conventions used
in rest of the package and make it easier for others to read/understand your code. Some of these conventions are
best practices that we have learnt over time.

- Use `numpy docstring`_ format for docstrings. Some parts of the code still use an older, unsupported format. If you
  happened to be modifying these methods, please change the docstring format as well.

- Don't write any code in ``__init__.py`` file

- Module-level logger variable must be named as ``LOG``

- If your method wants to report a failure, it *must* raise a custom exception. Built-in Python exceptions like
  ``TypeError``, ``KeyError`` are raised by Python interpreter and usually signify a bug in your code. Your method must
  not explicitly raise these exceptions because the caller has no way of knowing whether it came from a bug or not.
  Custom exceptions convey are must better at conveying the intent and can be handled appropriately by the caller.
  In HTTP lingo, custom exceptions are equivalent to 4xx (user's fault) and built-in exceptions are equivalent
  to 5xx (Service Fault)

- CLI commands must always raise a subclass of ``click.ClickException`` to signify an error. Error code and message
  must be set as a part of this exception and not explicitly returned by the CLI command.

- Don't use ``*args`` or ``**kwargs`` unless there is a really strong reason to do so. You must explain the reason
  in great detail in docstrings if you were to use them.

- Library classes, ie. the ones under ``lib`` folder, must **not** use Click.  Usage of Click must be restricted to
  the ``commands`` package. In the library package, your classes must expose interfaces that are independent
  of the user interface, be it a CLI thru Click, or CLI thru argparse, or HTTP API, or a GUI.

- Do not catch the broader ``Exception``, unless you have a really strong reason to do. You must explain the reason
  in great detail in comments.

Design Document
---------------

A design document is a written description of the feature/capability you are building. We have a
`design document template`_ to help you quickly fill in the blanks and get you working quickly. We encourage you to
write a design document for any feature you write, but for some types of features we definitely require a design
document to proceed with implementation.

**When do you need a design document?**

- Adding a new command
- Making a breaking change to CLI interface
- Refactoring code that alters the design of certain components
- Experimental features


.. _excellent cheatsheet: http://python-future.org/compatible_idioms.html
.. _pyenv: https://github.com/pyenv/pyenv
.. _tox: http://tox.readthedocs.io/en/latest/
.. _numpy docstring: https://numpydoc.readthedocs.io/en/latest/format.html
.. _pipenv: https://docs.pipenv.org/
.. _design document template: ./designs/_template.rst
