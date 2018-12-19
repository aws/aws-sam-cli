# Cookiecutter NodeJS Hello-world for SAM based Serverless App

![CI Build Status](https://travis-ci.org/aws-samples/cookiecutter-aws-sam-hello-nodejs.svg?branch=master)

A cookiecutter template to create a NodeJS Hello world boilerplate using [Serverless Application Model (SAM)](https://github.com/awslabs/serverless-application-model).

## Requirements

* [AWS SAM CLI](https://github.com/awslabs/aws-sam-cli)

## Usage

Generate a boilerplate template in your current project directory using the following syntax:

* **NodeJS 8**: `sam init --runtime nodejs8.10`
* **NodeJS 6**: `sam init --runtime nodejs6.10`

> **NOTE**: ``--name`` allows you to specify a different project folder name (`sam-app` is the default)

After generated you should have a new folder the following files:

```bash
sam-app                          <-- Project name with NodeJS boilerplate app
├── README.md
├── hello_world
│   ├── app.js
│   ├── package.json
│   └── tests
│       └── unit
│           └── test_handler.js
└── template.yaml
```

# Credits

* This project has been generated with [Cookiecutter](https://github.com/audreyr/cookiecutter)

