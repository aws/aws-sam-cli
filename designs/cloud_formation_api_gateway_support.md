# CloudFormation ApiGateway Support Design Doc

## The Problem

Customers use SAM CLI to run/test their applications by defining their resources in a SAM template. The raw CloudFormation ApiGateway resources are not currently supported to run and test locally in SAM CLI. The resource types include AWS::ApiGateway::* while ```sam local start-api``` only supports the AWS::Serverless::Api type. This prevents customers who have built/deployed services using the raw ApiGateway Resources or who have used tools to generate CloudFormation, like AWS CDK, from testing locally through SAM CLI. Specifically, Customers that generate their CloudFormation template using tools and have hand written CloudFormation templates have AWS::ApiGateway::* types preventing them from running locally. 

Customers that are able to test and run locally can find errors early, reduce development time, etc. If customers are not able to test, the development cycles will be very long with a process similar to write code, deploy, deploy failed, investigate, fix and repeat.

## Who are the Customers?

* People who work with tools such as AWS CDK, Terraform, and others to generate their CloudFormation templates
* People that have hand written CloudFormation templates with ApiGateway Resources

## Success criteria for the change

* Customers would be able to author SAM templates with Api Gateway Resources and test locally through start-api
* Feature parity with what is currently supported with start-api on the AWS::Serverless::Api Resource
* SAM CLI should support swagger and vanilla CloudFormation Api Gateway resources

Overall, SAM CLI should be able to seamlessly support local development and testing with the Api Gateway CloudFormation Resources.

## What will be changed?

When customers run ```sam local start-api``` with a template that uses raw CloudFormation AWS::ApiGateway::RestApi and AWS::ApiGateway::Stage resources, they will be able to interact and test their lambda functions as if they were using AWS::Serverless::Api.

## Out-of-Scope

Anything that SAM CLI doesn't currently support in SAM 
* ApiGateway Authorization such as resource policies, IAM roles/tags/policies, Lambda Authorizers, etc.
* ApiGateway CORS support 
* Proper validation of the CloudFormation templates so that it does smart validation and not just yaml parsing.

## User Experience Walkthrough

There are two main types of users who are going to benefit from this change.

* Customers can use tools such as AWS CDK to generate a template. The customer can create their AWS CDK project with `cdk init app` and then generate their CloudFormation code using `cdk synth.`They can input their CloudFormation code to test it locally using the SAM CLI command. 
* Customers can author CloudFormation resources and test them locally by inputting their templates into sam local start-api.

For both cases, The code can be run locally if they have CodeUri's pointing to valid local paths. 

Once the user has their  CloudFormation code, they will be running `sam local start-api --template /path/to/template.yaml`

# Implementation

## **Design**

There are a few approaches to supporting the new CloudFormation ApiGateway types such as ApiGateway::RestApi.

### *Approach #1*: Parsing both CloudFormation and SAM Resources

Appending to the current Sam Api code and to have dual support of both the CloudFormation Template and SAM template

Pros:
* This approach is something we do for lambda functions such as AWS::Lambda::Function and will provide consistency with our current implementation. 

Cons:
* Managing two different systems/templates require more work to resolve bugs. For example, supporting ApiGatewayV2, which supports web sockets with ApiGateway, the parsing of the template will need to be reimplemented in two places in order to support new functionality. One where it was defined using CloudFormation and the other where it was defined using the SAM template. This will slowly start to incur more and more technical debt as there is now more area to cover and duplication of work and resources. In the short term, it may be easier to implement, but in the long term there may be issues when dealing with support. 
* Another issue is that there may be escape hatches that are implemented in SAM causing additional effort to maintain differing parsing parts of the codebase.

### *Approach #2*: Process Once

Convert the SAM template into CloudFormation code and processes it once.

Pros:
* This simplifies a lot of the issues with approach #1. This will make it much easier to add and extend the system such as adding ApiGatewayV2, web sockets. The feature would only need to be added once instead of duplicated effort. 

Cons: 
* This will require more work in order to restructure the application such that the template is processed once after it processed to CloudFormation. 
* This could also produce bugs with issues if the SAM to CloudFormation transformation isn't correct in local testing. However, this may not matter as much since there is a direct translation of SAM resources to CloudFormation Resources and only a single point where the bug needs to be fixed.
* Possible imperfections of the SAM to CloudFormation conversion. In the past, some version of the transformation caused incompatible changes with the SAM CLI. If the conversion fails, it could cause users that are currently running their code locally to break. 
* The SAM Translator also requires credentials, which would now cause users to login before running a command. Credentials are currently required in sam validate because of this. A local flavor of the translator needs to be created in order to avoid the process.

### *Approach #3*: Abstraction

Extending the current code to a CloudFormationApiProvider object overriding the CloudFormation processing in certain methods. This will be doing two passes through the code. SAM code can be processed first and the CloudFormation types second.

Pros:
* This provides better abstraction, separating the CloudFormation code and the SamApi code. This can also be easily implemented.

Cons:
* This falls through the same pitfalls as approach #1. The abstraction for the same types may also be inconsistent with the way we are currently processing CloudFormation resources such as AWS::Lambda::Function.

### Approach RECOMMENDATION

Although other parts of the project are using approach #1 currently, I recommend using **approach #2**. It seems to cause the least technical debt in the long run and reduces our duplication of code. It may require some work to port some of the code from AWS::Lambda::Function to follow a similar format, but it may be worth in the long term. Since the act of translating the SAM to CloudFormation may be imperfect. I plan to first implement approach #1 and gradually move it to approach #2 once all the items are parsed. 

## **Design: Api Details**

### **AWS::ApiGateway::RestApi**

AWS::ApiGateway::RestApi will be one of the main resources defined in the CloudFormation template. It acts as the main definition for the Api. There are two approaches to consider for defining the RestApi template.

***Feature #1*: Swagger Method**
The swagger method is very similar to the support in our current code base. Swagger has many advantageous as it can be exported, do validation, etc. Customers can also link to the other files containing their swagger documentation. 

```yaml
ServerlessRestApi:
Type: 'AWS::ApiGateway::RestApi'
Properties:
  Body:
    basePath : /pete
    paths:
      /hello:
        get:
          x-amazon-apigateway-integration:
            httpMethod: POST
            type: aws_proxy
            uri: !Sub >-
              arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${HelloWorldFunction.Arn}/invocations
          responses: {}  
```

Swagger can also be inlined using the FN::Include Macro. This should also be supported while defining the CloudFormation template.
****Feature* #2*: Using a combination of AWS::ApiGateway::Resource with ApiGateway::Methods.**

Although this approach is less common and more verbose, it is still used by some people while defining their resources. Tools 
such as aws-cdk currently generate Resource and Methods ApiGateway CloudFormation Resources in their yaml instead of swagger. 

```yaml
UsersResource:
  Type: AWS::ApiGateway::Resource
  Properties:
    RestApiId:!Ref RestApi
    ParentId:
      Fn::GetAtt:
      - RestApi
      - RootResourceId
    PathPart: user
UsersGet:
  Type: AWS::ApiGateway::Method
  Properties:
    ResourceId: !Ref ApiGatewayResource
    RestApiId: !Ref ApiGatewayRestApi
    Integration:
      Type: AWS
      IntegrationHttpMethod: POST
      Uri:
        Fn::Join:
        - ''
        - - 'arn:aws:apigateway:'
          - Ref: AWS::Region
          - ":lambda:path/2015-03-31/functions/"
          - Fn::GetAtt:
            - Lambda
            - Arn
          - "/invocations"
      IntegrationResponses: []
    MethodResponses:
    - ResponseModels:
        application/json:
          Ref: UsersModel
      ResponseParameters:
        method.response.header.Link: true
      StatusCode: 200
   ApiGatewayMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      HttpMethod: POST
      Integration:
        ConnectionType: INTERNET
        IntegrationResponses:
          - ResponseTemplates:
              application/json: "{\"message\": \"OK\"}"
            StatusCode: 200
        RequestTemplates:
          applicationjson: "{\"statusCode\": $input.json('$.statusCode'), \"message\": $input.json('$.message')}"

```

The SAM template requires people to use only a single RestApi to define all of their resources.

### **AWS::ApiGateway::Stages**

The stage allows for defining environments for different parts of the pipeline in CloudFormation. Since a single stage is attached to a deployment, the behavior of multiple deployment/stages locally is currently undefined. 

Currently, the SAM template supports only one stage/one deployment and does not /<Stage>/<Serivce Name> as customers could want. One approach is to support additional flags in environments and stage names so they can test the apis locally in multiple environments. This would create a dict such as {“dev”: [models], “prod”: [models]}. However, this may be unnecessary. 

The AWS::ApiGateway::Stage will initially support the schema:

```yaml
Prod:
Type: AWS::ApiGateway::Stage
Properties:
  StageName: Prod
  Description: Prod Stage
  Variables:
    Stack: Prod
  RestApiId: RestApi`
```

Since the stages can show up in any order as the code is iterating through the resources, There are two approaches to consider too quickly stitch the api and stages together. 

*Approach #1:* 
Pick the last stage in the template that we find and use that on all the Apis
Pros: Similar to the current approach
Cons: The customer may not be able to view their environments in different stages.

*Approach: #2: *
Create a dictionary of all the stages and display the url as localhost:3000/<Stage Name>/routeName
Pros: This will allow people to view their code in different stages or environments.
Cons: This will require refactoring parts of the SamApiProvider that handles the Api. Customers usually don't use different stages to test and it may not be worth the effort to test. 

I recommend approach #1 as it follows the current standard and there is some data that very little people use the <Stage Name> when defining it. 

**AWS::ApiGateway::Deployment **
The deployment type defines which Apis objects should be available to the public. Normally, in the SAM template everything defined will have a deployment component, but the CloudFormation templates may have more bloat and information in them defining certain apis and deployments for Multi-stages.

One approach is to support multiple stages with multiple deployments and the code will filter out the stages that are not deployed or defined. One problem with this approach is that the RestApiId, a characteristic of the RestApi, for a deployment is only localhost and a single endpoint and the current schema doesn't allow deploying on multiple ports and multiple local domains. This will bring in unneeded complexity such as requiring the customer defining N valid ports and N valid domains.

Another approach, which I recommend, is to ignore the resource altogether as it always associated with a stage and to randomly pick a stage. 

## **Updating the code**

First, the Apis in AWS::ApiGateway::RestApi  will be parsed in the SAM Template in a similar way to the current AWS::Serverless:Api code. Stages and other Meta information in the Api will be parsed to support the CloudFormation template. The code will then be refactored to first translate the SAM templates inputted into the CloudFormation template using the SamTranslator. Once the Api code has been refactored, the function code can be refactored so that Serverless code is refactored out. 

Some pseudo classes and function for the implementation 

```python

class CloudFormationGatewayProvider(SamBaseProvider):
    # Same as serverless but update with ApiGateway Code
    _GATEWAY_REST_API = "AWS::ApiGateway::RestApi"
    _GATEWAY_STAGE_API = "AWS::ApiGateway::Stages"
    _GATEWAY_RESOURCE_API = "AWS::ApiGateway::Resource"
    _GATEWAY_METHODS_API = "AWS::ApiGateway::Method"
    
    def _extrac_api_gateway_rest_api():
        for logical_id, resource in resources.items():
            resource_type = resource.get(SamApiProvider._TYPE)
            # call method based on matching type
            
    # Detect Swagger or Method/Resource approach
    # Parse code similar to previous approach and update api dict
    # If the data is not swagger add the unfinished Api
    def _extract_gateway_rest_api():
         pass
         
    # set the method_name for the Api from AWS::ApiGateway::Methods
    def _extract_gateway_methods():
         pass
        
    # Set the stage for that api and its resources using AWS::ApiGateway::Stage
    def _extract_gateway_stage():
         pass
          
    # The alterate method for defining resources. This will parse the Api and update the path
    def _extract_gateway_resource():
        pass
        
    # Update the Api Model with the method name that corressponds to it.
    def _extract_gateway_method():
        pass                                                                                                                                                                                                                                                 
```

While updating the structure and flow of the code around Apis, parts of the flow about how the Api and Route is currently implemented can be updated to make updating future milestones like cors. Some examples include abstracting stage states and variables that exist in every route can be abstracted.

## CLI Changes

*Explain the changes to command line interface, including adding new commands, modifying arguments etc*
None 

### Breaking Change

*Are there any breaking changes to CLI interface? Explain*

None

## `.samrc` Changes

*Explain the new configuration entries, if any, you want to add to .samrc*

None

## Security

*Tip: How does this change impact security? Answer the following questions to help answer this question better:*
**What new dependencies (libraries/cli) does this change require?**
None

**What other Docker container images are you using?**
None

**Are you creating a new HTTP endpoint? If so explain how it will be created & used**
This will be used for local development.

**Are you connecting to a remote API? If so explain how is this connection secured**
No.

**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**
The setup is not written for local development.

# What is your Testing Plan (QA)?

## Goal

## Pre-Requisites

## Test Scenarios/Cases

* Basic Templates and unit tests to check that CloudFormation templates are covering the data
* Go through https://github.com/awslabs/serverless-application-model with tests/sample inputs and outputs.
* Create an example AWS Lambda Project with AWS CDK and test the generated CloudFormation code

## Expected Results

## Pass/Fail

# Documentation Changes

The main documentation change will be telling users that they are now allowed to pass SAM templates with ApiGateway resources.

# Open Issues

No open issues

# Task Breakdown

### Milestones:

**Milestone 1 Goal: Support Swagger and Stage Name with CloudFormation ApiGateway Resources**
Milestone #1A 

* Swagger Definition for AWS::ApiGateway works for RestApi

Milestone #1B:

* Support Stage Names/Variables, binary_media_types with AWS::ApiGatway

Milestone #1C:

* Support Non-inline swagger

Milestone #1D:

* Refactor Code to convert SAM into CloudFormationResource

**Milestone #2: Support Resource and Methods with CloudFormation ApiGateway Resources**

* Add Support for Resource and Methods parsing

### Time Breakdown

Milestone 1A ~ 1 Week

Milestone 1B ~ 1 Week

Milestone 1C ~ 2 day

Milestone 1D ~ 1 Week

Milestone 2 ~ 1 Week


