# {{ cookiecutter.project_name }}

This is a sample template for {{ cookiecutter.project_name }} - Below is a brief explanation of what we have generated for you:

```bash
.
├── README.md                   <-- This instructions file
├── hello_world                 <-- Source code for a lambda function
│   ├── __init__.py
│   └── app.py                  <-- Lambda function code
├── requirements.txt            <-- Python dependencies
├── template.yaml               <-- SAM template
└── tests                       <-- Unit tests
    └── unit
        ├── __init__.py
        └── test_handler.py
```

## Requirements

* AWS CLI already configured with at least PowerUser permission
{%- if cookiecutter.runtime == 'python3.6' %}
* [Python 3 installed](https://www.python.org/downloads/)
{%- else %}
* [Python 2.7 installed](https://www.python.org/downloads/)
{%- endif %}
* [Docker installed](https://www.docker.com/community-edition)
* [Python Virtual Environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/)

## Setup process

### Installing dependencies

[AWS Lambda requires a flat folder](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html) with the application as well as its dependencies. Therefore, we need to have a 2 step process in order to enable local testing as well as packaging/deployment later on - This consist of two commands you can run as follows:

```bash
pip install -r requirements.txt -t hello_world/build/
cp hello_world/*.py hello_world/build/
```

1. Step 1 install our dependencies into ``build`` folder 
2. Step 2 copies our application into ``build`` folder

**NOTE:** As you change your application code as well as dependencies during development you'll need to make sure these steps are repated in order to execute your Lambda and/or API Gateway locally.

### Local development

**Invoking function locally through local API Gateway**

```bash
sam local start-api
```

If the previous command ran successfully you should now be able to hit the following local endpoint to invoke your function `http://localhost:3000/hello`

**SAM CLI** is used to emulate both Lambda and API Gateway locally and uses our `template.yaml` to understand how to bootstrap this environment (runtime, where the source code is, etc.) - The following excerpt is what the CLI will read in order to initialize an API and its routes:

```yaml
...
Events:
    HelloWorld:
        Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
        Properties:
            Path: /hello
            Method: get
```

## Packaging and deployment

AWS Lambda Python runtime requires a flat folder with all dependencies including the application. SAM will use `CodeUri` property to know where to look up for both application and dependencies:

```yaml
...
    HelloWorldFunction:
        Type: AWS::Serverless::Function
        Properties:
            CodeUri: hello_world/
            ...
```

Firstly, we need a `S3 bucket` where we can upload our Lambda functions packaged as ZIP before we deploy anything - If you don't have a S3 bucket to store code artifacts then this is a good time to create one:

```bash
aws s3 mb s3://BUCKET_NAME
```

Next, run the following command to package our Lambda function to S3:

```bash
sam package \
    --template-file template.yaml \
    --output-template-file packaged.yaml \
    --s3-bucket REPLACE_THIS_WITH_YOUR_S3_BUCKET_NAME
```

Next, the following command will create a Cloudformation Stack and deploy your SAM resources.

```bash
sam deploy \
    --template-file packaged.yaml \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --capabilities CAPABILITY_IAM
```

> **See [Serverless Application Model (SAM) HOWTO Guide](https://github.com/awslabs/serverless-application-model/blob/master/HOWTO.md) for more details in how to get started.**

After deployment is complete you can run the following command to retrieve the API Gateway Endpoint URL:

```bash
aws cloudformation describe-stacks \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --query 'Stacks[].Outputs'
``` 

## Testing

We use **Pytest** for testing our code and you can install it using pip: ``pip install pytest`` 

Next, we run `pytest` against our `tests` folder to run our initial unit tests:

```bash
python -m pytest tests/ -v
```

**NOTE**: It is recommended to use a Python Virtual environment to separate your application development from  your system Python installation.

# Appendix

### Python Virtual environment

{%- if cookiecutter.runtime == 'python3.6' %}
**In case you're new to this**, python3 comes with `virtualenv` library by default so you can simply run the following:

1. Create a new virtual environment
2. Install dependencies in the new virtual environment

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
{%- else %}
**In case you're new to this**, python2 `virtualenv` module is not available in the standard library so we need to install it and then we can install our dependencies:

1. Create a new virtual environment
2. Install dependencies in the new virtual environment

```bash
pip install virtualenv
virtualenv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
{%- endif %}


**NOTE:** You can find more information about Virtual Environment at [Python Official Docs here](https://docs.python.org/3/tutorial/venv.html). Alternatively, you may want to look at [Pipenv](https://github.com/pypa/pipenv) as the new way of setting up development workflows
## AWS CLI commands

AWS CLI commands to package, deploy and describe outputs defined within the cloudformation stack:

```bash
sam package \
    --template-file template.yaml \
    --output-template-file packaged.yaml \
    --s3-bucket REPLACE_THIS_WITH_YOUR_S3_BUCKET_NAME

sam deploy \
    --template-file packaged.yaml \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides MyParameterSample=MySampleValue

aws cloudformation describe-stacks \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} --query 'Stacks[].Outputs'
```

## Bringing to the next level

Here are a few ideas that you can use to get more acquainted as to how this overall process works:

* Create an additional API resource (e.g. /hello/{proxy+}) and return the name requested through this new path
* Update unit test to capture that
* Package & Deploy

Next, you can use the following resources to know more about beyond hello world samples and how others structure their Serverless applications:

* [AWS Serverless Application Repository](https://aws.amazon.com/serverless/serverlessrepo/)
* [Chalice Python Serverless framework](https://github.com/aws/chalice)
* Sample Python with 3rd party dependencies, pipenv and Makefile: ``sam init --location https://github.com/aws-samples/cookiecutter-aws-sam-python``
