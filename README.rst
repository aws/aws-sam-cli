.. raw:: html

   <p align="center">

.. raw:: html

   </p>

SAM CLI (Beta)
==============

|Build Status| |Apache-2.0| |Contributers| |GitHub-release| |PyPI version|

`Join the SAM developers channel (#samdev) on
Slack <https://awssamopensource.splashthat.com/>`__ to collaborate with
fellow community members and the AWS SAM team.

**``sam``** is the AWS CLI tool for managing Serverless applications
written with `AWS Serverless Application Model
(SAM) <https://github.com/awslabs/serverless-application-model>`__. SAM
CLI can be used to test functions locally, start a local API Gateway
from a SAM template, validate a SAM template, generate sample payloads
for various event sources, and generate a SAM project in your favorite
Lambda Runtime.

-  `SAM CLI (Beta) <#sam-cli-beta>`__

   -  `Main features <#main-features>`__
   -  `Installation <#installation>`__

      -  `Prerequisites <#prerequisites>`__
      -  `Upgrade from 0.2.11 or Below <#upgrade-from-version-0-2-11-or-below>`__
      -  `Windows, Linux, macOS with PIP
         [Recommended] <#windows-linux-macos-with-pip-recommended>`__
      -  `Build From Source <#build-from-source>`__
      -  `Install with PyEnv <#install-with-pyenv>`__
      -  `Troubleshooting <#troubleshooting>`__

         -  `General <#general-issues>`__
         -  `Mac <#mac-issues>`__

   -  `Usage <#usage>`__

      -  `Invoke functions locally <#invoke-functions-locally>`__
      -  `Generate sample event source
         payloads <#generate-sample-event-source-payloads>`__
      -  `Run API Gateway locally <#run-api-gateway-locally>`__
      -  `Debugging Applications <#debugging-applications>`__

         -  `Debugging Python functions <#debugging-python-functions>`__

      -  `Validate SAM templates <#validate-sam-templates>`__
      -  `Package and Deploy to
         Lambda <#package-and-deploy-to-lambda>`__

   -  `Getting started <#getting-started>`__
   -  `Advanced <#advanced>`__

      -  `Compiled Languages <#compiled-languages>`__

         -  `Java <#java>`__
         -  `.NET Core <#net_core>`__

      -  `IAM Credentials <#iam-credentials>`__
      -  `Lambda Environment
         Variables <#lambda-environment-variables>`__

         -  `Environment Variable file <#environment-variable-file>`__
         -  `Shell environment <#shell-environment>`__
         -  `Combination of Shell and Environment Variable
            file <#combination-of-shell-and-environment-variable-file>`__

      -  `Identifying local execution from Lambda function
         code <#identifying-local-execution-from-lambda-function-code>`__
      -  `Static Assets <#static-assets>`__
      -  `Local Logging <#local-logging>`__
      -  `Remote Docker <#remote-docker>`__

   -  `Project Status <#project-status>`__
   -  `Contributing <#contributing>`__
   -  `A special thank you <#a-special-thank-you>`__
   -  `Examples <#examples>`__

Main features
-------------

-  Develop and test your Lambda functions locally with ``sam local`` and
   Docker
-  Invoke functions from known event sources such as Amazon S3, Amazon
   DynamoDB, Amazon Kinesis, etc.
-  Start local API Gateway from a SAM template, and quickly iterate over
   your functions with hot-reloading
-  Validate SAM templates
-  Get started with boilerplate Serverless Service in your chosen Lambda
   Runtime ``sam init``

Installation
------------

Prerequisites
~~~~~~~~~~~~~

- Docker
- Python2.7 (Python3+ not yet supported)

Running Serverless projects and functions locally with SAM CLI requires
Docker to be installed and running. SAM CLI will use the ``DOCKER_HOST``
environment variable to contact the docker daemon.

-  macOS: `Docker for
   Mac <https://store.docker.com/editions/community/docker-ce-desktop-mac>`__
-  Windows: `Docker
   Toolbox <https://download.docker.com/win/stable/DockerToolbox.exe>`__
-  Linux: Check your distro’s package manager (e.g. yum install docker)

For macOS and Windows users: SAM CLI requires that the project directory
(or any parent directory) is listed in Docker file sharing options.

Verify that docker is working, and that you can run docker commands from
the CLI (e.g. ‘docker ps’). You do not need to install/fetch/pull any
containers – SAM CLI will do it automatically as required.

Upgrade from Version 0.2.11 or Below
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uninstall previous CLI Version

.. code:: bash

    npm uninstall -g aws-sam-local

To upgrade to Version 0.3.0 or above, follow instructions below:

Windows, Linux, macOS with PIP [Recommended]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verify Python Version is 2.7.

.. code:: bash
    python --version

The easiest way to install **``sam``** is to use
`PIP <https://pypi.org/>`__.

.. code:: bash

   pip install --user aws-sam-cli

Verify the installation worked:

.. code:: bash

   sam --version

Upgrading via pip
^^^^^^^^^^^^^^^^^

To update **``sam``** once installed via pip:

.. code:: bash

   pip install --user --upgrade aws-sam-cli

Build From Source
~~~~~~~~~~~~~~~~~

First, install Python(2.7) on your machine, then run the following:

.. code:: bash

   # Clone the repository
   $ git clone git@github.com:awslabs/aws-sam-cli.git

   # cd into the git
   $ cd aws-sam-cli

   # pip install the repository
   $ pip install --user -e .

Install with PyEnv
~~~~~~~~~~~~~~~~~~
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
    $ sam –version

Troubleshooting
~~~~~~~~~~~~~~~

General Issues
^^^^^^^^^^^^^^

1. If you are seeing `sam command not found`, this is likely due to the installation using the `--user` and
   adding `sam` to a path that is not in your $PATH.

.. code:: bash

    # Find your path Python User Base path (where Python --user will install packages/scripts)
    USER_BASE_PATH="$(python -m site --user-base)"

    # Add this path to your $PATH
    export PATH=$USER_BASE_PATH:$PATH

You can also try an installing aws-sam-cli without `--user`

.. code:: bash

    # Uninstall aws-sam-cli from the --user path
    pip uninstall --user aws-sam-cli

    pip install aws-sam-cli

Mac Issues
^^^^^^^^^^

1. **[Errno 13] Permission denied** If you had installed Python using
   Homebrew, you might need to use ``sudo`` to install SAM CLI:

.. code:: bash

   sudo pip install aws-sam-cli

1. **TLSV1_ALERT_PROTOCOL_VERSION**:

If you get an error something similar to:

::

   Could not fetch URL https://pypi.python.org/simple/click/: There was a problem confirming the ssl certificate: [SSL: TLSV1_ALERT_PROTOCOL_VERSION] tlsv1 alert protocol version (_ssl.c:590) - skipping

then you are probably using the default version of Python that came with
your Mac. This is outdated. So make sure you install Python again using
homebrew and try again:

.. code:: bash

   brew install python@2

Followed by:

.. code:: bash

   pip install --user aws-sam-cli

Usage
-----

**``sam``** requires a SAM template in order to know how to invoke your
function locally, and it’s also true for spawning API Gateway locally -
If no template is specified ``template.yaml`` will be used instead.

You can create a sample app by running the command ``sam init --runtime <your-favorite-runtime>``
or find other sample SAM Templates by visiting `SAM <https://github.com/awslabs/serverless-application-model>`__ official repository.

Invoke functions locally
~~~~~~~~~~~~~~~~~~~~~~~~

.. figure:: media/sam-invoke.gif
   :alt: SAM CLI Invoke Sample

   SAM CLI Invoke Sample

You can invoke your function locally by passing its **SAM logical ID**
and an event file. Alternatively, ``sam local invoke`` accepts stdin as
an event too.

.. code:: yaml

   Resources:
     Ratings:  # <-- Logical ID
       Type: 'AWS::Serverless::Function'
     ...

**Syntax**

.. code:: bash

   # Invoking function with event file
   $ sam local invoke "Ratings" -e event.json

   # Invoking function with event via stdin
   $ echo '{"message": "Hey, are you there?" }' | sam local invoke "Ratings"

   # For more options
   $ sam local invoke --help

Generate sample event source payloads
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To make local development and testing of Lambda functions easier, you
can generate mock/sample event payloads for the following services:

-  S3
-  Kinesis
-  DynamoDB
-  Cloudwatch Scheduled Event
-  Cloudtrail
-  API Gateway

**Syntax**

.. code:: bash

   sam local generate-event <service>

Also, you can invoke an individual lambda function locally from a sample
event payload - Here’s an example using S3:

.. code:: bash

   sam local generate-event s3 --bucket <bucket> --key <key> | sam local invoke <function logical id>

For more options, see ``sam local generate-event --help``.

Run API Gateway locally
~~~~~~~~~~~~~~~~~~~~~~~

``sam local start-api`` spawns a local API Gateway to test HTTP
request/response functionality. Features hot-reloading to allow you to
quickly develop, and iterate over your functions.

.. figure:: media/sam-start-api.gif
   :alt: SAM CLI Start API

   SAM CLI Start API

**Syntax**

.. code:: bash

   sam local start-api

**``sam``** will automatically find any functions within your SAM
template that have ``Api`` event sources defined, and mount them at the
defined HTTP paths.

In the example below, the ``Ratings`` function would mount
``ratings.py:handler()`` at ``/ratings`` for ``GET`` requests.

.. code:: yaml

   Ratings:
     Type: AWS::Serverless::Function
     Properties:
       Handler: ratings.handler
       Runtime: python3.6
       Events:
         Api:
           Type: Api
           Properties:
             Path: /ratings
             Method: get

By default, SAM uses `Proxy
Integration <http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-api-as-simple-proxy-for-lambda.html>`__
and expects the response from your Lambda function to include one or
more of the following: ``statusCode``, ``headers`` and/or ``body``.

For example:

.. code:: javascript

   // Example of a Proxy Integration response
   exports.handler = (event, context, callback) => {
       callback(null, {
           statusCode: 200,
           headers: { "x-custom-header" : "my custom header value" },
           body: "hello world"
       });
   }

For examples in other AWS Lambda languages, see `this
page <http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-api-as-simple-proxy-for-lambda.html>`__.

If your function does not return a valid `Proxy
Integration <http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-api-as-simple-proxy-for-lambda.html>`__
response then you will get a HTTP 500 (Internal Server Error) when
accessing your function. SAM CLI will also print the following error log
message to help you diagnose the problem:

::

   ERROR: Function ExampleFunction returned an invalid response (must include one of: body, headers or statusCode in the response object)

Debugging Applications
~~~~~~~~~~~~~~~~~~~~~~

Both ``sam local invoke`` and ``sam local start-api`` support local
debugging of your functions.

To run SAM Local with debugging support enabled, just specify
``--debug-port`` or ``-d`` on the command line.

.. code:: bash

   # Invoke a function locally in debug mode on port 5858
   $ sam local invoke -d 5858 <function logical id>

   # Start local API Gateway in debug mode on port 5858
   $ sam local start-api -d 5858

Note: If using ``sam local start-api``, the local API Gateway will
expose all of your Lambda functions but, since you can specify a single
debug port, you can only debug one function at a time. You will need to
hit your API before SAM CLI binds to the port allowing the debugger to
connect.

Here is an example showing how to debug a NodeJS function with Microsoft
Visual Studio Code:

.. figure:: media/sam-debug.gif
   :alt: SAM Local debugging example

   SAM Local debugging example

In order to setup Visual Studio Code for debugging with AWS SAM CLI, use
the following launch configuration:

::

   {
       "version": "0.2.0",
       "configurations": [
           {
               "name": "Attach to SAM Local",
               "type": "node",
               "request": "attach",
               "address": "localhost",
               "port": 5858,
               "localRoot": "${workspaceRoot}",
               "remoteRoot": "/var/task",
               "protocol": "legacy"
           }
       ]
   }

Note: Node.js versions **below** 7 (e.g. Node.js 4.3 and Node.js 6.10)
use the ``legacy`` protocol, while Node.js versions including and above
7 (e.g. Node.js 8.10) use the ``inspector`` protocol. Be sure to specify
the corresponding protocol in the ``protocol`` entry of your launch
configuration.

Debugging Python functions
^^^^^^^^^^^^^^^^^^^^^^^^^^

Unlike Node.JS and Java, Python requires you to enable remote debugging
in your Lambda function code. If you enable debugging with
``--debug-port`` or ``-d`` for a function that uses one of the Python
runtimes, SAM CLI will just map through that port from your host machine
through to the Lambda runtime container. You will need to enable remote
debugging in your function code. To do this, use a python package such
as `remote-pdb <https://pypi.python.org/pypi/remote-pdb>`__. When
configuring the host the debugger listens on in your code, make sure to
use ``0.0.0.0`` not ``127.0.0.1`` to allow Docker to map through the
port to your host machine.

   Please note, due to a `open
   bug <https://github.com/Microsoft/vscode-python/issues/71>`__ with
   Visual Studio Code, you may get a
   ``Debug adapter process has terminated unexpectedly`` error when
   attempting to debug Python applications with this IDE. Please track
   the `GitHub
   issue <https://github.com/Microsoft/vscode-python/issues/71>`__ for
   updates.

Passing Additional Runtime Debug Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To pass additional runtime arguments when debugging your function, use
the environment variable ``DEBUGGER_ARGS``. This will pass a string
of arguments directly into the run command SAM CLI uses to start your
function.

For example, if you want to load a debugger like iKPdb at runtime of
your Python function, you could pass the following as
``DEBUGGER_ARGS``:
``-m ikpdb --ikpdb-port=5858 --ikpdb-working-directory=/var/task/ --ikpdb-client-working-directory=/myApp --ikpdb-address=0.0.0.0``.
This would load iKPdb at runtime with the other arguments you’ve
specified. In this case, your full SAM CLI command would be:

.. code:: bash

   $ DEBUGGER_ARGS="-m ikpdb --ikpdb-port=5858 --ikpdb-working-directory=/var/task/ --ikpdb-client-working-directory=/myApp --ikpdb-address=0.0.0.0" echo {} | sam local invoke -d 5858 myFunction

You may pass debugger arguments to functions of all runtimes.

Connecting to docker network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both ``sam local invoke`` and ``sam local start-api`` support connecting
the create lambda docker containers to an existing docker network.

To connect the containers to an existing docker network, you can use the
``--docker-network`` command-line argument or the ``SAM_DOCKER_NETWORK``
environment variable along with the name or id of the docker network you
wish to connect to.

.. code:: bash

   # Invoke a function locally and connect to a docker network
   $ sam local invoke --docker-network my-custom-network <function logical id>

   # Start local API Gateway and connect all containers to a docker network
   $ sam local start-api --docker-network b91847306671 -d 5858

Validate SAM templates
~~~~~~~~~~~~~~~~~~~~~~

Validate your templates with ``$ sam validate``. Currently this command
will validate that the template provided is valid JSON / YAML. As with
most SAM CLI commands, it will look for a ``template.[yaml|yml]`` file
in your current working directory by default. You can specify a
different template file/location with the ``-t`` or ``--template``
option.

**Syntax**

.. code:: bash

   $ sam validate
   <path-to-file>/template.yml is a valid SAM Template

Note: The validate command requires AWS credentials to be configured. See `IAM Credentials <#iam-credentials>`__.

Package and Deploy to Lambda
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have developed and tested your Serverless application locally,
you can deploy to Lambda using ``sam package`` and ``sam deploy``
command. ``package`` command will zip your code artifacts, upload to S3
and produce a SAM file that is ready to be deployed to Lambda using AWS
CloudFormation. ``deploy`` command will deploy the packaged SAM template
to CloudFormation. Both ``sam package`` and ``sam deploy`` are identical
to their AWS CLI equivalents commands
```aws cloudformation package`` <http://docs.aws.amazon.com/cli/latest/reference/cloudformation/package.html>`__
and
```aws cloudformation deploy`` <http://docs.aws.amazon.com/cli/latest/reference/cloudformation/deploy/index.html>`__
respectively. Please consult the AWS CLI command documentation for
usage.

Example:

.. code:: bash

   # Package SAM template
   $ sam package --template-file sam.yaml --s3-bucket mybucket --output-template-file packaged.yaml

   # Deploy packaged SAM template
   $ sam deploy --template-file ./packaged.yaml --stack-name mystack --capabilities CAPABILITY_IAM

Getting started
---------------

-  Check out our `Getting Started Guide <docs/getting_started.rst>`__ for more details

Advanced
--------

Compiled Languages
~~~~~~~~~~~~~~~~~~~~~~~~~

**Java**

To use SAM CLI with compiled languages, such as Java that require a
packaged artifact (e.g. a JAR, or ZIP), you can specify the location of
the artifact with the ``AWS::Serverless::Function`` ``CodeUri`` property
in your SAM template.

For example:

::

   AWSTemplateFormatVersion: 2010-09-09
   Transform: AWS::Serverless-2016-10-31

   Resources:
     ExampleJavaFunction:
       Type: AWS::Serverless::Function
       Properties:
         Handler: com.example.HelloWorldHandler
         CodeUri: ./target/HelloWorld-1.0.jar
         Runtime: java8

You should then build your JAR file using your normal build process.
Please note that JAR files used with AWS Lambda should be a shaded JAR
file (or uber jar) containing all of the function dependencies.

::

   // Build the JAR file
   $ mvn package shade:shade

   // Invoke with SAM Local
   $ echo '{ "some": "input" }' | sam local invoke

   // Or start local API Gateway simulator
   $ sam local start-api


**.NET Core**

To use SAM Local with compiled languages, such as .NET Core that require a packaged artifact (e.g. a ZIP), you can specify the location of the artifact with the ``AWS::Serverless::Function`` ``CodeUri`` property in your SAM template.

For example:

.. code:: yaml

   AWSTemplateFormatVersion: 2010-09-09
   Transform: AWS::Serverless-2016-10-31

   Resources:
     ExampleDotNetFunction:
       Type: AWS::Serverless::Function
       Properties:
         Handler: HelloWorld::HelloWorld.Function::Handler
         CodeUri: ./artifacts/HelloWorld.zip
         Runtime: dotnetcore2.0

You should then build your ZIP file using your normal build process.

You can generate a .NET Core example by using the ``sam init --runtime dotnetcore`` command.

.. _IAMCreds

IAM Credentials
~~~~~~~~~~~~~~~

SAM CLI will invoke functions with your locally configured IAM
credentials.

As with the AWS CLI and SDKs, SAM CLI will look for credentials in the
following order:

1. Environment Variables (``AWS_ACCESS_KEY_ID``,
   ``AWS_SECRET_ACCESS_KEY``).
2. The AWS credentials file (located at ``~/.aws/credentials`` on Linux,
   macOS, or Unix, or at ``C:\Users\USERNAME \.aws\credentials`` on
   Windows).
3. Instance profile credentials (if running on Amazon EC2 with an
   assigned instance role).

In order to test API Gateway with a non-default profile from your AWS
credentials file append ``--profile <profile name>`` to the
``start-api`` command:

::

   // Test API Gateway locally with a credential profile.
   $ sam local start-api --profile some_profile

See this `Configuring the AWS
CLI <http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#config-settings-and-precedence>`__
for more details.

Lambda Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your Lambda function uses environment variables, you can provide
values for them will passed to the Docker container. Here is how you
would do it:

For example, consider the SAM template snippet:

.. code:: yaml


   Resources:
     MyFunction1:
       Type: AWS::Serverless::Function
       Properties:
         Handler: index.handler
         Runtime: nodejs4.3
         Environment:
           Variables:
             TABLE_NAME: prodtable
             BUCKET_NAME: prodbucket

     MyFunction2:
       Type: AWS::Serverless::Function
       Properties:
         Handler: app.handler
         Runtime: nodejs4.3
         Environment:
           Variables:
             STAGE: prod
             TABLE_NAME: prodtable


Environment Variable file
^^^^^^^^^^^^^^^^^^^^^^^^^

Use ``--env-vars`` argument of ``invoke`` or ``start-api`` commands to
provide a JSON file that contains values for environment variables
defined in your function. The file should be structured as follows:

.. code:: json

   {
     "MyFunction1": {
       "TABLE_NAME": "localtable",
       "BUCKET_NAME": "testBucket"
     },
     "MyFunction2": {
       "TABLE_NAME": "localtable",
       "STAGE": "dev"
     },
   }

.. code:: bash

   $ sam local start-api --env-vars env.json


Shell environment
^^^^^^^^^^^^^^^^^

Variables defined in your Shell’s environment will be passed to the
Docker container, if they map to a Variable in your Lambda function.
Shell variables are globally applicable to functions ie. If two
functions have a variable called ``TABLE_NAME``, then the value for
``TABLE_NAME`` provided through Shell’s environment will be availabe to
both functions.

Following command will make value of ``mytable`` available to both
``MyFunction1`` and ``MyFunction2``

.. code:: bash

   $ TABLE_NAME=mytable sam local start-api

Combination of Shell and Environment Variable file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For greater control, you can use a combination shell variables and
external environment variable file. If a variable is defined in both
places, the one from the file will override the shell. Here is the order
of priority, highest to lowest. Higher priority ones will override the
lower.

1. Environment Variable file
2. Shell’s environment
3. Hard-coded values from the template

Identifying local execution from Lambda function code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When your Lambda function is invoked using SAM CLI, it sets an
environment variable ``AWS_SAM_LOCAL=true`` in the Docker container.
Your Lambda function can use this property to enable or disable
functionality that would not make sense in local development. For
example: Disable emitting metrics to CloudWatch (or) Enable verbose
logging etc.

Static Assets
~~~~~~~~~~~~~

Often, it’s useful to serve up static assets (e.g CSS/HTML/Javascript
etc) when developing a Serverless application. On AWS, this would
normally be done with CloudFront/S3. SAM CLI by default looks for a
``./public/`` directory in your SAM project directory and will serve up
all files from it at the root of the HTTP server when using
``sam local start-api``. You can override the default static asset
directory by using the ``-s`` or ``--static-dir`` command line flag. You
can also disable this behaviour completely by setting
``--static-dir ""``.

Local Logging
~~~~~~~~~~~~~

Both ``invoke`` and ``start-api`` command allow you to pipe logs from
the function’s invocation into a file. This will be useful if you are
running automated tests against SAM CLI and want to capture logs for
analysis.

Example:

.. code:: bash

   $ sam local invoke --log-file ./output.log

Remote Docker
~~~~~~~~~~~~~

Sam CLI loads function code by mounting filesystem to a Docker Volume.
As a result, The project directory must be pre-mounted on the remote
host where the Docker is running.

If mounted, you can use the remote docker normally using
``--docker-volume-basedir`` or environment variable
``SAM_DOCKER_VOLUME_BASEDIR``.

Example - Docker Toolbox (Windows):

When you install and run Docker Toolbox, the Linux VM with Docker is
automatically installed in the virtual box.

The /c/ path for this Linux VM is automatically shared with C: on the
host machine.

.. code:: powershell

   sam local invoke --docker-volume-basedir /c/Users/shlee322/projects/test "Ratings"

Project Status
--------------

-  [ ] Python Versions support

   -  [x] Python 2.7
   -  [ ] Python 3.6

-  [ ] Supported AWS Lambda Runtimes

   -  [x] ``nodejs``
   -  [x] ``nodejs4.3``
   -  [x] ``nodejs6.10``
   -  [x] ``nodejs8.10``
   -  [x] ``java8``
   -  [x] ``python2.7``
   -  [x] ``python3.6``
   -  [ ] ``dotnetcore1.0``
   -  [x] ``dotnetcore2.0``

-  [x] AWS credential support
-  [x] Debugging support
-  [x] Inline Swagger support within SAM templates
-  [x] Validating SAM templates locally
-  [x] Generating boilerplate templates

   -  [x] ``nodejs``
   -  [x] ``nodejs4.3``
   -  [x] ``nodejs6.10``
   -  [x] ``nodejs8.10``
   -  [x] ``java8``
   -  [x] ``python2.7``
   -  [x] ``python3.6``
   -  [x] ``dotnetcore1.0``
   -  [x] ``dotnetcore2.0``

Contributing
------------

Contributions and feedback are welcome! Proposals and pull requests will
be considered and responded to. For more information, see the
`CONTRIBUTING <CONTRIBUTING.md>`__ file.

A special thank you
-------------------

SAM CLI uses the open source
`docker-lambda <https://github.com/lambci/docker-lambda>`__ Docker
images created by [@mhart](https://github.com/mhart).


.. raw:: html

   <!-- Links -->

.. |Build Status| image:: https://travis-ci.org/awslabs/aws-sam-local.svg?branch=develop
.. |Apache-2.0| image:: https://img.shields.io/npm/l/aws-sam-local.svg?maxAge=2592000
.. |Contributers| image:: https://img.shields.io/github/contributors/awslabs/aws-sam-local.svg?maxAge=2592000
.. |GitHub-release| image:: https://img.shields.io/github/release/awslabs/aws-sam-local.svg?maxAge=2592000
.. |PyPI version| image:: https://badge.fury.io/py/aws-sam-cli.svg

