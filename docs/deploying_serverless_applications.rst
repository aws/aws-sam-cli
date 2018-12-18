Once you have created a Lambda function and a template.yaml file, you can use the AWS CLI to package and deploy your serverless application.

Packaging and deploying your application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to complete the procedures below, you need to first complete the following:

 `Set up an AWS Account <https://docs.aws.amazon.com/lambda/latest/dg/setup.html>`__.

 `Set up the AWS CLI <https://docs.aws.amazon.com/lambda/latest/dg/setup-awscli.html>`__ .

Packaging your application
~~~~~~~~~~~~~~~~~~~~~~~~~~
To package your application, create an Amazon S3 bucket that the package command will use to upload your ZIP deployment package (if you haven't specified one in your example.yaml file). You can use the following command to create the Amazon S3 bucket:

.. code:: bash

    aws s3 mb s3://bucket-name --region <region-name>

Next, open a command prompt and type the following:

.. code:: bash

    sam package \
        --template-file path/template.yaml \
        --output-template-file serverless-output.yaml \
        --s3-bucket s3-bucket-name

The package command returns an AWS SAM template named serverless-output.yaml that contains the CodeUri that points to the deployment zip in the Amazon S3 bucket that you specified. This template represents your serverless application. You are now ready to deploy it.

Deploying your application
~~~~~~~~~~~~~~~~~~~~~~~~~~

To deploy the application, run the following command:

.. code:: bash

    sam deploy \
        --template-file serverless-output.yaml \
        --stack-name new-stack-name \
        --capabilities CAPABILITY_IAM

Note that the value you specify for the --template-file parameter is the name of the SAM template that was returned by the package command. In addition, the --capabilities parameter is optional. The AWS::Serverless::Function resource will implicitly create a role to execute the Lambda function if one is not specified in the template. You use the --capabilities parameter to explicitly acknowledge that AWS CloudFormation is allowed to create roles on your behalf.

When you run the aws sam deploy command, it creates an AWS CloudFormation ChangeSet, which is a list of changes to the AWS CloudFormation stack, and then deploys it. Some stack templates might include resources that can affect permissions in your AWS account, for example, by creating new AWS Identity and Access Management (IAM) users. For those stacks, you must explicitly acknowledge their capabilities by specifying the --capabilities parameter.

To verify your results, open the AWS CloudFormation console to view the newly created AWS CloudFormation stack and the Lambda console to view your function.

Learn More
==========

-  `Project Overview <../README.rst>`__
-  `Installation <installation.rst>`__
-  `Getting started with SAM and the SAM CLI <getting_started.rst>`__
-  `Usage <usage.rst>`__
-  `Advanced <advanced_usage.rst>`__
