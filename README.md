# SAM CLI

![sam-banner.png](./sam-banner.png)

`sam` is the AWS CLI tool for managing Serverless applications written with the open source [AWS Serverless Application Model (AWS SAM)](https://github.com/awslabs/serverless-application-model). 

It makes developing, testing and deploying Serverless applications a breeze. It let's you easily do things like:

 - Develop and test your Lambda functions locally with `$ sam local` and Docker.
 
 - Generate sample function payloads (e.g. S3 event) and test individual functions locally:
 
 `$ sam local generate-event s3 --bucket <bucket> --key <key> | sam local invoke <function name>` 
 
 - Spawn a local API Gateway to test HTTP request/response functionality. Features hot-reloading to allowing you to quickly develop and iterate on your functions.
 
 `$ sam local start-api`

 - Validate your templates with `$ sam validate`.

 - Package and deploy your applications to AWS with `$ aws cloudformation package` and `$ aws cloudformation deploy`.


## Getting Started

The AWS Serverless Application Model (AWS SAM) is a fast and easy way of deploying your Serverless projects. It lets you write simple templates to describe your functions, and their event sources (API Gateway, S3, Kinesis etc).

Let's imagine we want to build a simple RESTful API to list, create, read, update and delete products. We'll start by laying out our project directory like so:

```
├── products.js
└── template.yaml
```

The `template.yaml` file is the AWS SAM template. Let's start by describing a single Lambda function to handle all of our API requests to `/products`.

```yaml
AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: My first serverless application.

Resources:
            
  Products:
    Type: AWS::Serverless::Function
    Properties:
      Handler: products.handler
      Runtime: nodejs6.10
      Events:
        ListProducts:
          Type: Api
          Properties:
            Path: /products
            Method: get
        CreateProduct:
          Type: Api
          Properties:
            Path: /products
            Method: post
        Product:
          Type: Api
          Properties:
            Path: /products/{product}
            Method: any

```

In the above example, we're configuring the following RESTful API endpoints:

 - Create new product with a `PUT` request to `/products`.
 - List all products with a `GET` request to `/products`.
 - Read, update or delete a product with `GET`, `PUT` or `DELETE` request to `/products/{product}`. 

In order to service these, let's create a Lambda function in `products.js` like so:

```javascript
'use strict';

exports.handler = (event, context, callback) => {

    let id = event.pathParameters.product || false;
    switch(event.httpMethod){
        
        case "GET":
            
            if(id) {
                callback(null, "This is a READ operation on product ID " + id);
                return;  
            } 
            
            callback(null, "This is a LIST operation, return all products");
            break;
            
        case "POST":
            callback(null, "This is a CREATE operation");
            break;

        case "PUT": 
            callback(null, "This is a UPDATE operation on product ID " + id);
            break;
             
        case "DELETE": 
            callback(null, "This is a DELETE operation on product ID " + id);
            break;

        default:
            // Send HTTP 501: Not Implemented
            console.log("Error: unsupported HTTP method (" + event.httpMethod + ")");
            callback(null, { statusCode: 501 })
            
    }

}
```

We can quickly run this locally with SAM CLI, to help us iterate quickly on development:

```bash
$ sam local start-api

2017/05/18 14:03:01 Successfully parsed template.yaml (AWS::Serverless-2016-10-31)
2017/05/18 14:03:01 Found 1 AWS::Serverless::Function
2017/05/18 14:03:01 Mounting products.handler (nodejs6.10) at /products [POST]
2017/05/18 14:03:01 Mounting products.handler (nodejs6.10) at /products/{product} [OPTIONS GET HEAD POST PUT DELETE TRACE CONNECT]
2017/05/18 14:03:01 Mounting products.handler (nodejs6.10) at /products [GET]
2017/05/18 14:03:01 Listening on http://localhost:3000

You can now browse to the above endpoints to invoke your functions.
You do not need to restart/reload while working on your functions,
changes will be reflected instantly/automatically. You only need to restart
if you update your AWS SAM template.
```

Now we can test our API endpoint locally either with a browser, or the CLI:

```bash
$ curl http://localhost:3000/products 
"This is a LIST operation, return all products"

$ curl -XDELETE http://localhost:3000/products/1
"This is a DELETE operation on product ID 1"
```

Any logging output (e.g. `console.log()`, as well as the AWS Lambda runtime logs are displayed by the SAM CLI. For example, in our code above we are logging an error message if an unsupported HTTP method is called. 

Let's test this by calling our API with an unsupported HTTP method:

```bash
$ curl -XOPTIONS http://localhost:3000/products/1
*   Trying ::1...
* TCP_NODELAY set
* Connected to localhost (::1) port 3000 (#0)
> OPTIONS /products/1 HTTP/1.1
> Host: localhost:3000
> User-Agent: curl/7.51.0
> Accept: */*
>
< HTTP/1.1 501 Not Implemented
< Content-Type: application/json
< Date: Thu, 18 May 2017 13:18:57 GMT
< Content-Length: 0
<
```

If we look back at the AWS SAM output, we can see our log entry:

```
START RequestId: 2137da9a-c79c-1d43-5716-406b4e6b5c0a Version: $LATEST
2017-05-18T13:18:57.852Z        2137da9a-c79c-1d43-5716-406b4e6b5c0a    Error: unsupported HTTP method (OPTIONS)
END RequestId: 2137da9a-c79c-1d43-5716-406b4e6b5c0a
REPORT RequestId: 2137da9a-c79c-1d43-5716-406b4e6b5c0a  Duration: 12.78 ms      Billed Duration: 100 ms Memory Size: 0 MB       Max Memory Used: 29 MB
```

When you are developing, any changes to your AWS Lambda function code are reflected instantly - no need to restart `sam local start-api`.

When you're ready to deploy your Serverless application to AWS, it's easy to package and deploy via the AWS CLI using `aws cloudformation package` and `aws cloudformation deploy`. You can read more 

Or, you can easily setup a full CI/CD pipeline with AWS CodePipeline to automate your software delivery process using [AWS CodeStar](https://aws.amazon.com/blogs/aws/new-aws-codestar/).

## Developing other (non-API) Serverless Applications

SAM CLI supports generation of mock Serverless events, allowing you to develop and test locally on functions that respond to asynchronous events such as those from S3, Kinesis, or DynamoDB.

You can use the `sam local generate-event` command to create these events:

```bash
$ sam local generate-event
NAME:
   sam local generate-event - Generates Lambda events (e.g. for S3/Kinesis etc) that can be piped to 'sam local invoke'

USAGE:
   sam local generate-event command [command options] [arguments...]

COMMANDS:
     s3        Generates a sample Amazon S3 event
     sns       Generates a sample Amazon SNS event
     kinesis   Generates a sample Amazon Kinesis event
     dynamodb  Generates a sample Amazon DynamoDB event
     api       Generates a sample Amazon API Gateway event
     schedule  Generates a sample scheduled event

OPTIONS:
   --help, -h  show help
``` 

For example, to locally test a function that recieves an S3 event, you could run:

```
$ sam local generate-event s3 --bucket <bucket> --key <key> | sam local invoke <function name>
```


## Installation

### OSX

The easiest way to install `sam` on OSX is to use [Homebrew](https://brew.sh/).
Make sure you're on the Amazon network, then run the following:

```
$ brew tap amazon/amazon ssh://git.amazon.com/pkg/HomebrewAmazon
$ brew install aws-sam-cli --HEAD
$ sam --version
```

### Other

`sam` will run on Windows and Linux, but you'll need to build it from scratch.

First, install Go (v1.8+) on your machine: [https://golang.org/doc/install](https://golang.org/doc/install), then run the following:

```
$ go install github.com/awslabs/aws-sam-cli 
// TODO: Cross platform installation instructions here...
```

This will install `sam` to your $GOPATH/bin folder. Make sure this directory is in your `$PATH` (or %%PATH%% on Windows) and you should then be able to use the SAM CLI.

```
$ sam --help
```


### Sample functions & SAM template

If you're looking for an AWS SAM project to play around with `sam`, take a look here:
[https://drive.corp.amazon.com/documents/pmaddox@/Shared/sam-demo-template-1.0.0.zip](https://drive.corp.amazon.com/documents/pmaddox@/Shared/sam-demo-template-1.0.0.zip)

## Project Status
  
- [ ] Supported AWS Lambda Runtimes
  - [x] `nodejs`
  - [x] `nodejs4.3`
  - [x] `nodejs6.10`
  - [ ] `java8`
  - [x] `python2.7`
  - [x] `python3.6`
  - [ ] `dotnetcore1.0`
  - [ ] `nodejs4.3-edge`
- [x] AWS credential support
- [ ] Inline Swagger support within SAM templates

## Contributing
