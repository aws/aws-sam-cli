
==============
Advanced Usage
==============


Compiled Languages
------------------

**Java**

To use SAM CLI with compiled languages, such as Java that require a
packaged artifact (e.g. a JAR, or ZIP), you can specify the location of
the artifact with the ``AWS::Serverless::Function`` ``CodeUri`` property
in your SAM template.

For example:

.. code:: yaml

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

.. code:: bash

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
---------------

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

.. code:: bash

   // Test API Gateway locally with a credential profile.
   $ sam local start-api --profile some_profile

See this `Configuring the AWS
CLI <http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#config-settings-and-precedence>`__
for more details.

Lambda Environment Variables
----------------------------

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
-------------------------

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
-----------------

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
--------------------------------------------------

For greater control, you can use a combination shell variables and
external environment variable file. If a variable is defined in both
places, the one from the file will override the shell. Here is the order
of priority, highest to lowest. Higher priority ones will override the
lower.

1. Environment Variable file
2. Shell’s environment
3. Hard-coded values from the template

Identifying local execution from Lambda function code
-----------------------------------------------------

When your Lambda function is invoked using SAM CLI, it sets an
environment variable ``AWS_SAM_LOCAL=true`` in the Docker container.
Your Lambda function can use this property to enable or disable
functionality that would not make sense in local development. For
example: Disable emitting metrics to CloudWatch (or) Enable verbose
logging etc.

Static Assets
-------------

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
-------------

Both ``invoke`` and ``start-api`` command allow you to pipe logs from
the function’s invocation into a file. This will be useful if you are
running automated tests against SAM CLI and want to capture logs for
analysis.

Example:

.. code:: bash

   $ sam local invoke --log-file ./output.log

Remote Docker
-------------

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

   $ sam local invoke --docker-volume-basedir /c/Users/shlee322/projects/test "Ratings"

Learn More
==========

-  `Project Overview <README.rst>`__
-  `Installation <installation.rst>`__
-  `Usage <usage.rst>`__