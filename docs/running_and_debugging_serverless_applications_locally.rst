Running and debugging serverless applications locally
=====================================================
SAM CLI works with AWS SAM, allowing you to invoke functions defined in SAM templates, whether directly or through API Gateway endpoints. By using SAM CLI, you can analyze your SAM application's performance in your own testing environment and update accordingly.

Invoking Lambda functions locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

    # Invoking function with event file

    $ echo '{"message": "Hey, are you there?" }' | sam local invoke "Ratings"

    # For more options

    $ sam local invoke --help


Running API Gateway Locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~
start-api: Creates a local HTTP server hosting all of your Lambda functions. When accessed by using a browser or the CLI, this operation launches a Docker container locally to invoke your function. It reads the CodeUri property of the AWS::Serverless::Function resource to find the path in your file system containing the Lambda function code. This path can be the project's root directory for interpreted languages like Node.js or Python, a build directory that stores your compiled artifacts, or for Java, a .jar file.

If you use an interpreted language, local changes are made available within the same Docker container. This approach means you can reinvoke your Lambda function with no need for redeployment.

invoke: Invokes a local Lambda function once and terminates after invocation completes.

.. code::

    $ sam local start-api

    2018-05-08 08:48:38 Mounting HelloWorld at http://127.0.0.1:3000/ [GET]
    2018-05-08 08:48:38 Mounting HelloWorld at http://127.0.0.1:3000/thumbnail [GET]
    2018-05-08 08:48:38 You can now browse to the above endpoints to invoke your functions. You do not need to restart/reload SAM CLI while working on your functions changes will be reflected instantly/automatically. You only need to restart SAM CLI if you update your AWS SAM template
    2018-05-08 08:48:38  * Running on http://127.0.0.1:3000/ (Press CTRL+C to quit)

Debugging With SAM CLI
~~~~~~~~~~~~~~~~~~~~~~

Both sam local invoke and sam local start-api support local debugging of your functions. To run SAM CLI with debugging support enabled, specify --debug-port or -d on the command line.

.. code:: bash

    # Invoke a function locally in debug mode on port 5858

    $ sam local invoke -d 5858 function logical id

    # Start local API Gateway in debug mode on port 5858

    $ sam local start-api -d 5858

If you use sam local start-api, the local API Gateway exposes all of your Lambda functions. But because you can specify only one debug port, you can only debug one function at a time.

Connecting a Debugger to your IDE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For compiled languages or projects requiring complex packing support, we recommend that you run your own build solution and point AWS SAM to the directory that contains the build dependency files needed. You can use the following IDEs or one of your choosing.

- Cloud9
- Eclipse
- Visual Studio Code

Integrating other services
~~~~~~~~~~~~~~~~~~~~~~~~~~
You can use the AWS Serverless Application Model to integrate other services as event sources to your application. For example, assume you have an application that requires a Dynamo DB table. The following shows an example:

.. code:: yaml

    AWSTemplateFormatVersion: '2010-09-09'
    Transform: AWS::Serverless-2016-10-31
    Resources:
      ProcessDynamoDBStream:
        Type: AWS::Serverless::Function
        Properties:
          Handler: handler
          Runtime: runtime
          Policies: AWSLambdaDynamoDBExecutionRole
          Events:
            Stream:
              Type: DynamoDB
              Properties:
                Stream: !GetAtt DynamoDBTable.StreamArn
                BatchSize: 100
                StartingPosition: TRIM_HORIZON

      DynamoDBTable:
        Type: AWS::DynamoDB::Table
        Properties:
          AttributeDefinitions:
            - AttributeName: id
              AttributeType: S
          KeySchema:
            - AttributeName: id
              KeyType: HASH
          ProvisionedThroughput:
            ReadCapacityUnits: 5
            WriteCapacityUnits: 5
          StreamSpecification:
            StreamViewType: NEW_IMAGE

Validate your SAM template
~~~~~~~~~~~~~~~~~~~~~~~~~~
You can use SAM CLI to validate your template against the official AWS Serverless Application Model specification. The following is an example if you specify either an unsupported runtime or deprecated runtime version.

.. code::

    $ sam validate

    Error: Invalid Serverless Application Specification document. Number of errors found: 1. Resource with id [SkillFunction] is invalid. property Runtim not defined for resource of type AWS::Serverless::Function

    $ sed -i 's/Runtim/Runtime/g` template.yaml

    $ sam validate
    template.yaml is a valid SAM Template

