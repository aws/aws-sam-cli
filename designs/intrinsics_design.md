# Intrinsic Function Support Design Doc

## The Problem

Customers can define their CloudFormation resources in many ways. Intrinsic Functions allow for greater templating and modularity of the CloudFormation template by injecting properties at runtime.  Intrinsic Functions have the properties `Fn::Base64, Fn::FindInMap, Ref, Fn::Join, etc.`  This is also true in the SAM template, which supports a small parts of the Intrinsic functions. Although customers use a variety of attributes like Fn::Join, Ref regularly, SAM-CLI is unable to run and resolve it locally. This prevents customers from testing and running their code locally, leading in frustration and problems.

Intrinsic Functions are also used in many of the tools that generate CloudFormation. For example, AWS-CDK generates their CloudFormation resources using `Fn::Join, Fn::GetAtt, Ref` with AWS::ApiGateway::Resource and AWS::ApiGateway::Methods, which fails to resolve and run locally. Supporting this will allow for greater interoperability with other tools, creating a better local developer experience.

In terms of resolving intrinsic properties, there are no other tools for local space. This makes it difficult for other tools to build any code that has intrinsic functions. 

## Who are the Customers?

* Customers who work with tools such as Serverless, AWS CDK, Terraform, and others to generate their CloudFormation templates due to the increased interoperability with SAM-CLI
* Customers who create tools such as Serverless, AWS CDK, etc. to resolve Intrinsic properties to create their systems, improving the developer tooling space.
* Customers who work create SAM/CloudFormation templates that involve intrinsics

## Success criteria for the change

* The intrinsic properties Fn::Base64, Fn::And, Fn::Equals, Fn::If ,Fn::Not. Fn::Or, Fn::GetAtt, Fn::GetAZs, Fn::Join, Fn::Select, Fn::Split, Fn::Sub, Ref will all work locally, mirroring the attributes CloudFormation does.
* AWS-CDK and Serverless generate templates that can be processed and run locally directly within SAM-CLI

## What will be changed?

The code will now recursively parse the different intrinsic function properties and resolve them at runtime.

## Out-of-Scope

The following intrinsics are out of scope:

* Macros with Fn::Transform other than AWS::Include
* Fn::ImportValue and dealing with nested stacks
* Fn::Cidr 
* The service based intrinsics https://docs.aws.amazon.com/servicecatalog/latest/adminguide/intrinsic-function-reference-rules.html

## User Experience Walkthrough
The customer can input a CloudFormation template into SAM-CLI containing intrinsic functions like `Fn::Join, Fn::GetAtt, Ref`. This includes sam build, sam local start-api, etc. 

Example walkthrough with `sam local start-api`: 
* Customers can use tools such as AWS CDK to generate a template. The templates will have intrinsic properties. The customer can create their AWS CDK project with `cdk init app` and then generate their CloudFormation code using `cdk synth.`They can input their CloudFormation code to test it locally using the SAM CLI command. 
* Customers can author CloudFormation resources with intrinsics functions and test them locally by inputting their templates into sam local start-api.

Once the user has their  CloudFormation code, they will be running `sam local start-api --template /path/to/template.yaml`

# Implementation

## Intrinsic Function Properties

### Fn::Join

```
{ "Fn::Join" : [ "delimiter", [ comma-delimited list of values ] ] }
!Join [ "delimiter", [comma-delimited list of values ] ]``
```

This intrinsic function will first verify the objects are a list.
Then for every item in the list, it will recursively run the intrinsic function resolver.
After verifying the types, It will join the items in the list together based on the string. 

### Fn::Split

```
{ "Fn::Split" : [ "delimiter", "source string" ] }
!Split `[ "delimiter", "source string" ]``
```

This intrinsic function will recursively resolve every item in the list and then split the source string based on the delimiter.

### Fn::Base64

```
{ "Fn::Base64" : `valueToEncode` }
!Base64 valueToEncode
```

This intrinsic function will resolve the valueToEncode property and then run a python base64 encode on the returned string.

### Fn::Select

```
{ "Fn::Select" : [ index, listOfObjects ] }
!Select [ index, listOfObjects]``
```

This intrinsic function will recursively resolve every item in the list and verify the type of the index element. Then it will select a single item from the listOfObjects that were resolved.

### Fn:::GetAzs

```
Fn::GetAZs: !Ref 'AWS::Region'`
```

This intrinsic function will find the region from the reference property and return a list of availability zones. This will be a lookup in this dictionary

```
regions = {"us-east-1": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"],           "us-west-1": ["us-west-1b", "us-west-1c"],           "eu-north-1": ["eu-north-1a", "eu-north-1b", "eu-north-1c"],           "ap-northeast-3": ["ap-northeast-3a"],           "ap-northeast-2": ["ap-northeast-2a", "ap-northeast-2b", "ap-northeast-2c"],           "ap-northeast-1": ["ap-northeast-1a", "ap-northeast-1c", "ap-northeast-1d"],           "sa-east-1": ["sa-east-1a", "sa-east-1c"],           "ap-southeast-1": ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"],           "ca-central-1": ["ca-central-1a", "ca-central-1b"],           "ap-southeast-2": ["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"],           "us-west-2": ["us-west-2a", "us-west-2b", "us-west-2c", "us-west-2d"],           "us-east-2": ["us-east-2a", "us-east-2b", "us-east-2c"],           "ap-south-1": ["ap-south-1a", "ap-south-1b", "ap-south-1c"],           "eu-central-1": ["eu-central-1a", "eu-central-1b", "eu-central-1c"],           "eu-west-1": ["eu-west-1a", "eu-west-1b", "eu-west-1c"],           "eu-west-2": ["eu-west-2a", "eu-west-2b", "eu-west-2c"],           "eu-west-3": ["eu-west-3a", "eu-west-3b", "eu-west-3c"],           "cn-north-1": []}
```

### Fn::GetAtt

```
"Fn::GetAtt": ["logical_id", "resource_property_type"]
!GetAtt ["logical_id", "resource_property_type"]
```

This intrinsic function is one of the harder properties to resolve as it can be injected at runtime. 
There is a list of supported properties at https://d1uauaxba7bl26.cloudfront.net/latest/gzip/CloudFormationResourceSpecification.json. 
These properties will be read and verified if existed in the ResourceSpecification. In strings, they are usually represented as ${MyInstance.PublicIp}.
Different Types have different parameters attached with them. 

After parsing the logical_id and resource_property_type, a separate symbol table can be used to translate logical_id and resource_id into the injected runtime property.
The symbol resolver will be passed in at runtime separate from the intrinsic_resolver. 


### `Fn::Sub`

```
{ "Fn::Sub" : String } or { "Fn::Sub" : [string, "{test}", "{test2}"] }
```

This intrinsic does string substitution. Both types are supported. For the string, Regex will be used to replace the property of the string with the variables that are refs or pseudo refs such as ${AWS::RegionName}. This same process is done with the list, but every item in the list is recursively resolved and then approached the same way. 

### Fn::Transform

```
Fn::Transform
```

This allows for transforming properties of properties from one format to another. This can allow for many different macro types. However, only *AWS::INCLUDE* is in scope for this project. 

```
{
    "Fn::Transform": {
        "Name": "AWS::Include",
        "Parameters": {
            "Location": "s3://MyAmazonS3BucketName/swagger.yaml"
        }
    }
}
```

We currently parse this format to figure out the location of the swagger. However, the location paramater can also be resolved as a ref. All that’s left is to run the recursive resolver.

### Ref

```
Ref: logicalName
or
!Ref logicalName
```

This intrinsics allows for getting the reference to another resource or parameter. Locally, if it’s a pseudo parameter we should be able to generate a random resolution or come up with the best possible alternative.
These can also be resolved at runtime, so it’s best to make them dynamic functions that are passed in. Unresolved items can be returned as a string of the format ${}. 

Different Types have different parameters attached with them. This feels like it needs to be hardcoded for each one. This can be built dynamically

### Fn::FindInMap

```
{ "Fn::FindInMap" : [ "MapName", "TopLevelKey", "SecondLevelKey"] }
```

This resource allows for finding keys and values in a Mappings dictionary. This requires recurcively resolving each property and then getting the property. 

## Boolean Intrinsic Logic

Customers can also specify boolean logic when trying to resolve the templates. These include Fn::And, Fn::Equals,Fn::If, and Fn::Not. This requires parsing the parameters section and the Conditionals section in the CloudFormation template. When called, the condition needs to be resolved based on the parameters. 

### FN::And

```
"Fn::And": [{condition}, {...}]
```

This will recursively resolve every property in the list in Fn::And and verify each one returns a boolean true value. The items in the list support both other Intrinsics like Fn::Equals or conditionals of the format {Conditional: ConditionName}.

### FN::Equals

```
"Fn::Equals" : ["value_1", "value_2"]
```

This will check that both items in the list will recursively resolve to the same thing. This will return a boolean value.

### FN::If

```
"Fn::If": [condition_name, value_if_true, value_if_false]
```

This intrinsic boolean property will first resolve every item in the list, resolving the Conditions part of the template and then selecting value_if_true or value_if_false depending on the attribute.

### FN::Not

```
"Fn::Not": [{condition}]
```

This intrinsic function will resolve the condition in the list and then return the opposite boolean value returned. 

### FN::Or

```
"Fn::Or": [{condition}, {...}]
```

This intrinsic function is very similar to the Fn::And function, but will check that at least one of the items in the last returns a truthy value. 

## Pseudo Parameters

Pseudo Parameters are predefined by AWS CloudFormation such as the AccountId and such. These will be resolved separately and is heavily used with Refs!. 
If the item is specified as an environment setting optionally or it is specified in the Parameter section it will be read there. 
Otherwise, These will be resolved whenever a !Ref Psuedo Paramater or Ref: Psuedo Paramater or ${Psuedo Paramater} is in the template.

The default values for parameters will be
```python
    _DEFAULT_PSEUDO_PARAM_VALUES = {
        "AWS::AccountId": "123456789012",
        "AWS::Partition": "aws",

        "AWS::Region": "us-east-1",

        "AWS::StackName": "local",
        "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/"
                        "local/51af3dc0-da77-11e4-872e-1234567db123",
        "AWS::URLSuffix": "localhost"
    }
```
### AWS::AccountId

This will be a account id from the __DEFAULT_PSEUDO_PARAM_VALUES.

### AWs::NotificationArns

This property can be randomly generated to follow the format

### AWS::NoValue

This will return the None python value.

### AWS::Partition

This is resource specific and separates regions like US and China into subgroups. This will be found in a large dictionary.

### AWS::REGION

This property will first be attempted to be read from the environment settings. Otherwise, It will use the default region.

### AWS::StackId

This will be a stack id from the __DEFAULT_PSEUDO_PARAM_VALUES.


### AWS::StackName

This will be a stack name from the __DEFAULT_PSEUDO_PARAM_VALUES.

### AWS::URLSuffix

This will be replaces by the corresponding [amazonaws.com](http://amazonaws.com/) or [amazonaws.com.cn](http://amazonaws.com.cn/) depending on the region settings. This will be found in a dictionary. 

## Implementing the Code

This can be separated into a IntrinsicsResolver and a SymbolResolver. The SymbolResolver is an abstraction that holds all the translation of the references and attributes inside the template. 
The IntrinsicsResolver will recursively parse the template and all the attributes and the symbol table will be injected in at runtime. 

### Intrinsic Symbol Table

* logical_id_translator: This will be used as an exact translation for translating pseudo/logical_id types

* default_type_resolver: This will be in the following form, resolving the type

```
{
    "AWS::ApiGateway::RestApi": {
        "RootResourceId": "/"
    }
}
```

* common_attribute_resolver: resolves common attributes that will be true across all

```
{    "Ref": lambda p,r: "",
     "Arn:": arn_resolver}
```


First pseudo types are checked. If item is present in the logical_id_translator it is returned. Otherwise, it falls back to the default_pseudo_resolver. 

Then the default_type_resolver is checked, which has common attributes and functions for each types.
 
Then the common_attribute_resolver is run, which has functions that are common for each attribute.

### Intrinsic Resolver

The will be the core part of the resolver, which will be recursively called.

```
def intrinsic_property_resolver():
    if key in self.intrinsic_key_function_map:
        # process intrinsic function
    elif key in self.conditional_key_function_map:
        # process conditional
    else:
        # In this case, it is a dictionary that doesn't directly contain an intrinsic resolver and must be
        # re-parsed to resolve.
```

The template will be resolved item by item

```
processed_template = {}
for key, val in self.resources.items():
    processed_key = self.symbol_resolver.get_translation(key, IntrinsicResolver.REF) or key

    processed_resource = self.intrinsic_property_resolver(val)
    processed_template[processed_key] = processed_resource
```
If there is an error with the resource, the item will be ignored and processed. This is because we don't want to break any workflows that have errors with unresolved symbol tables. This is especially true for refs that exist to cloud instances. The error will be printed in the console tho. 
Currently, in SAM these properties are ignored and would not cause any errors, so by ignoring the errors we are using the same functionality. To ignore the error, we just copy the resource as is.

## Integration into SAM-CLI

This can be very easily plugged into the current SAM-CLI code. This needs to be run after the SamBaseTranslator runs. This will go through every property and check if it requires intrinsic resolution. 

This can also be plugged in into specific areas such as the Body section of a Api and the Uri section in a function to handle the Arn. 

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

## Validation

The validation logic is baked into the code, by verifying at each step that it has the right type and the items in it.

## Goal

Test the main combinations of intrinsic functions in order to verify that the functions are lazily resolving correctly.

## Test Scenarios/Cases

# Documentation Changes

None

# Open Issues

https://github.com/awslabs/aws-sam-cli/issues/1079
https://github.com/awslabs/aws-sam-cli/issues/1038
https://github.com/awslabs/aws-sam-cli/issues/826
https://github.com/awslabs/aws-sam-cli/issues/476
https://github.com/awslabs/aws-sam-cli/issues/194


# Task Breakdown

### Milestones:

**Milestone 1 Goal: Support The Basic Intrinsic Properties other than Fn::GetAtt, Fn::ImportValue, and Ref**

**Milestone 2 Goal: Support Boolean Properties such as Fn::If, Fn::And, Fn::Or, etc.**

**Milestone 3 Goal: Support Refs and GetAtt with runtime plugins**

**Milestone 4 Goals: Organize code so that it can be pluggable by multiple libraries easily**

### Time Breakdown

Milestone 1 ~ 1 Week

Milestone 2 ~ 1 Week

Milestone 3 ~ 1 Week

Milestone 4 ~ 1 Week


