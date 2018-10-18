==============
Installation
==============

Prerequisites
-------------

- Docker
- Python2.7 or Python3.6
- `The AWS CLI <https://aws.amazon.com/cli/>`__

Running Serverless projects and functions locally with SAM CLI requires
Docker to be installed and running. SAM CLI will use the ``DOCKER_HOST``
environment variable to contact the docker daemon.

-  **macOS**: `Docker for
   Mac <https://store.docker.com/editions/community/docker-ce-desktop-mac>`__
-  **Windows**: `Docker
   For Windows (create an account & follow through to download from the Docker Store) <https://www.docker.com/docker-windows>`__
-  **Linux**: Check your distro’s package manager (e.g. yum install docker)
      *** for Centos 7.5 System requirements are::
         yum install gcc zip py-pip py-setuptools ca-certificates groff  python-dev g++ make docker epel-release python-pip python-devel\
                     python-tools
          **run post install of above**
          pip install --upgrade pip
          pip install --upgrade setuptools
          pip install --upgrade aws-sam-cli
        *** if you want to use the lambda-local option(without running it as root) you will need to add your user to the docker group ***
         usermod -a -G Docker yourUserName
     
**Note for macOS and Windows users**: SAM CLI requires that the project directory
(or any parent directory) is listed in `Docker file sharing options <https://docs.docker.com/docker-for-mac/osxfs/>`__.

Verify that docker is working, and that you can run docker commands from
the CLI (e.g. `docker ps`). You do not need to install/fetch/pull any
containers – SAM CLI will do it automatically as required.

Using PIP
---------

**Step 1.**  Verify Python Version is 2.7 or 3.6.


.. code:: bash

    $ python --version
 
If not installed, go `download python and install <https://www.python.org/downloads/>`_

**Step 2.** Verify Pip is installed. 

The easiest way to install ``sam`` is to use
`PIP <https://pypi.org/>`__.

.. code:: bash

    $ pip --version

If not installed, `download and install pip <https://pip.pypa.io/en/stable/installing/>`_

**Step 3.** Install aws-sam-cli

.. code:: bash

   $ pip install --user aws-sam-cli

**Step 4.** **Adjust your PATH** to include Python scripts installed under User's directory.

macOS & Linux
^^^^^^^^^^^^^

In Unix/Mac systems the command ``python -m site --user-base`` typically print ``~/.local`` path, so that you'll need to add ``/bin`` to obtain the script path

**NOTE**: As explained in the `Python Developer's Guide <https://www.python.org/dev/peps/pep-0370/#specification>`__, the User's directory where the scripts are installed is ``~/.local/bin`` for Unix/Mac.


.. code:: bash

    # Find your Python User Base path (where Python --user will install packages/scripts)
    $ USER_BASE_PATH=$(python -m site --user-base)

    # Update your preferred shell configuration
    -- Standard bash --> ~/.bash_profile
    -- ZSH           --> ~/.zshrc
    $ export PATH=$PATH:$USER_BASE_PATH/bin

Restart or Open up a new terminal and verify that the installation worked:

.. code:: bash

   # Restart current shell
   $ exec "$SHELL"
   $ sam --version
   
Windows
^^^^^^^

In Windows systems the command ``py -m site --user-site`` typically print ``%APPDATA%\Roaming\Python<VERSION>\site-packages``, so you'll need to remove the last ``\site-packages`` folder and replace it with the ``\Scripts`` one.

.. code:: bash

   $ python -m site --user-base
   
Using file explorer, go to the folder indicated in the output, and look for the ``Scripts`` folder. Visually confirm that sam Application is inside this folder. 

Copy the File Path.

**NOTE**: As explained in the `Python Developer's Guide <https://www.python.org/dev/peps/pep-0370/#specification>`__, the User's directory where the scripts are installed is ``%APPDATA%\Python\Scripts`` for Windows.

Seach Windows for ``Edit the system environment variables``.

Select **Environmental Variables**.

Under **System variables**, select **Path**.

Select **New** and enter the file path to the Python Scripts folder. 

**Step 5.** Verify that sam is installed

Restart or Open up a new terminal and verify that the installation worked:

.. code:: bash

   # Restart current shell
   $ sam --version

Upgrading
---------

``sam`` can be upgraded via pip:

.. code:: bash

   $ pip install --user --upgrade aws-sam-cli

Previous CLI Versions must be uninstalled first (0.2.11 or below) and then follow the `Installation <#windows-linux-macos-with-pip>`__ steps above:

.. code:: bash

   $ npm uninstall -g aws-sam-local

Advanced installations
----------------------

Build From Source
^^^^^^^^^^^^^^^^^

First, install Python(2.7 or 3.6) on your machine, then run the following:

.. code:: bash

   # Clone the repository
   $ git clone git@github.com:awslabs/aws-sam-cli.git

   # cd into the git
   $ cd aws-sam-cli

   # pip install the repository
   $ pip install --user -e .

Install with PyEnv
^^^^^^^^^^^^^^^^^^

.. code:: bash

    # Install PyEnv (https://github.com/pyenv/pyenv#installation)
    $ brew update
    $ brew install pyenv

    # Initialize pyenv using bash_profile
    $ echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi\nexport PATH="~/.pyenv/bin:$PATH"' >> ~/.bash_profile
    # or using zshrc
    $ echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi\nexport PATH="~/.pyenv/bin:$PATH"' >> ~/.zshrc

    # restart the shell
    $ exec "$SHELL"

    # Install Python 2.7
    $ pyenv install 2.7.14
    $ pyenv local 2.7.14

    # Install the CLI
    $ pip install --user aws-sam-cli

    # Verify your installation worked
    $ sam –-version

Updating SAM CLI on AWS Cloud9
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your AWS Cloud9 environment has a SAM CLI version < 0.3.0 installed there are a few extra steps you must do to upgrade to newer versions:

.. code:: bash

    # Uninstall the older version of SAM Local
    $ npm uninstall -g aws-sam-local
   
    # Remove the symlink 
    $ rm -rf $(which sam)
   
    # Install the CLI
    $ pip install --user aws-sam-cli
   
    # Create new symlink
    $ ln -sf $(which sam) ~/.c9/bin/sam
    
    # Reset the bash cache
    $ hash -r
   
    # Verify your installation worked
    $ sam –-version

Troubleshooting
---------------

Mac Issues
^^^^^^^^^^

1. **TLSV1_ALERT_PROTOCOL_VERSION**:

If you get an error something similar to:

::

   Could not fetch URL https://pypi.python.org/simple/click/: There was a problem confirming the ssl certificate: [SSL: TLSV1_ALERT_PROTOCOL_VERSION] tlsv1 alert protocol version (_ssl.c:590) - skipping

then you are probably using the default version of Python that came with
your Mac. This is outdated. So make sure you install Python again using
homebrew and try again:

.. code:: bash

   $ brew install python

Once installed then repeat the `Installation process <#windows-linux-macos-with-pip>`_

Learn More
==========

-  `Project Overview <../README.rst>`__
-  `Getting started with SAM and the SAM CLI <getting_started.rst>`__
-  `Usage <usage.rst>`__
-  `Packaging and deploying your application <deploying_serverless_applications.rst>`__
-  `Advanced <advanced_usage.rst>`__
