# AWS GoFormation

[![Build Status](https://travis-ci.org/awslabs/goformation.svg?branch=0.1.0)](https://travis-ci.org/awslabs/goformation) [![GoDoc Reference](https://godoc.org/gopkg.in/awslabs/goformation.v1?status.svg)](http://godoc.org/github.com/awslabs/goformation) ![Apache-2.0](https://img.shields.io/badge/Licence-Apache%202.0-blue.svg) 

`GoFormation` is a Go library for working with AWS CloudFormation / AWS Serverless Application Model (SAM) templates. 
- [AWS GoFormation](#aws-goformation)
    - [Main features](#main-features)
    - [Installation](#installation)
    - [Usage](#usage)
        - [Marhsalling CloudFormation/SAM described with Go structs, into YAML/JSON](#marhsalling-cloudformationsam-described-with-go-structs-into-yamljson)
        - [Unmarhalling CloudFormation YAML/JSON into Go structs](#unmarhalling-cloudformation-yamljson-into-go-structs)
    - [Updating CloudFormation / SAM Resources in GoFormation](#updating-cloudformation-sam-resources-in-goformation)
    - [Advanced](#advanced)
        - [AWS CloudFormation Intrinsic Functions](#aws-cloudformation-intrinsic-functions)
            - [Resolving References (Ref)](#resolving-references-ref)
            - [Warning: YAML short form intrinsic functions (e.g. !Sub)](#warning-yaml-short-form-intrinsic-functions-eg-sub)
    - [Contributing](#contributing)

## Main features

 * Describe AWS CloudFormation and AWS SAM templates as Go objects (structs), and then turn it into JSON/YAML.
 * Parse JSON/YAML AWS CloudFormation and AWS SAM templates and turn them into Go structs.
 * Strongly typed Go structs generated for every AWS CloudFormation and AWS SAM resource.
 * Automatically generated, from the published AWS CloudFormation Resource Specification.

## Installation

As with other Go libraries, GoFormation can be installed with `go get`.

```
$ go get github.com/awslabs/goformation
```

## Usage

### Marhsalling CloudFormation/SAM described with Go structs, into YAML/JSON

Below is an example of building a CloudFormation template programatically, then outputting the resulting JSON

```go
package main

import (
    "fmt"
    "github.com/awslabs/goformation"
    "github.com/awslabs/goformation/cloudformation"
)

func main() {

    // Create a new CloudFormation template
    template := cloudformation.NewTemplate()

    // An an example SNS Topic
    template.Resources["MySNSTopic"] = cloudformation.AWSSNSTopic{
        DisplayName: "test-sns-topic-display-name",
        TopicName:   "test-sns-topic-name",
        Subscription: []cloudformation.AWSSNSTopic_Subscription{
            cloudformation.AWSSNSTopic_Subscription{
                Endpoint: "test-sns-topic-subscription-endpoint",
                Protocol: "test-sns-topic-subscription-protocol",
            },
        },
    }

    // ...and a Route 53 Hosted Zone too
    template.Resources["MyRoute53HostedZone"] = cloudformation.AWSRoute53HostedZone{
        Name: "example.com",
    }

    // Let's see the JSON
    j, err := template.JSON() 
    if err != nil {
        fmt.Printf("Failed to generate JSON: %s\n", err)
    } else {
        fmt.Print(j)
    }
  
    y, err := template.YAML()
    if err != nil {
        fmt.Printf("Failed to generate JSON: %s\n", err)
    } else {
        fmt.Print(y)
    }

}
```

Would output the following JSON template

```javascript
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Resources": {
    "MyRoute53HostedZone": {
      "Name": "example.com"
    },
    "MySNSTopic": {
      "DisplayName": "test-sns-topic-display-name",
      "Subscription": [
        {
          "Endpoint": "test-sns-topic-subscription-endpoint",
          "Protocol": "test-sns-topic-subscription-protocol"
        }
      ],
      "TopicName": "test-sns-topic-name"
    }
  }
}
```

...and the following YAML template

```yaml
AWSTemplateFormatVersion: 2010-09-09
Resources:
  MyRoute53HostedZone:
    Name: example.com
  MySNSTopic:
    DisplayName: test-sns-topic-display-name
    Subscription:
    - Endpoint: test-sns-topic-subscription-endpoint
      Protocol: test-sns-topic-subscription-protocol
    TopicName: test-sns-topic-name
```


### Unmarhalling CloudFormation YAML/JSON into Go structs 

GoFormation also works the other way - parsing JSON/YAML CloudFormation/SAM templates into Go structs.

```go
package main

import (
    "fmt"
    "github.com/awslabs/goformation"
    "github.com/awslabs/goformation/cloudformation"
)

func main() {

    // Open a template from file (can be JSON or YAML)
    template, err := goformation.Open("template.yaml")

    // ...or provide one as a byte array ([]byte)
    template, err := goformation.Parse(data)

    // You can then inspect all of the values
    for name, resource := range template.Resources {

        // E.g. Found a resource with name MyLambdaFunction and type AWS::Lambda::Function
        log.Printf("Found a resource with name %s and type %s", name, resource.Type)

    }

    // You can extract all resources of a certain type
    // Each AWS CloudFormation / SAM resource is a strongly typed struct
    functions := template.GetAllAWSLambdaFunctionResources()
    for name, function := range functions {

        // E.g. Found a AWS::Lambda::Function with name MyLambdaFunction and nodejs6.10 handler 
        log.Printf("Found a %s with name %s and %s handler", name, function.Type(), function.Handler)

    }

}
```

## Updating CloudFormation / SAM Resources in GoFormation
 
AWS GoFormation contains automatically generated Go structs for every CloudFormation/SAM resource, located in the [cloudformation/](cloudformation/) directory. These can be generated, from the latest [AWS CloudFormation Resource Specification](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-resource-specification.html) published for `us-east-1` by just running `go generate`:

```
$ go generate

Generated 587 AWS CloudFormation resources from specification v1.4.2
Generated 17 AWS SAM resources from specification v2016-10-31
Generated JSON Schema: schema/cloudformation.schema.json
```

Our aim is to automatically update GoFormation whenever the AWS CloudFormation Resource Specification changes, via an automated pull request to this repository. This is not currently in place. 

## Advanced

### AWS CloudFormation Intrinsic Functions

The following [AWS CloudFormation Intrinsic Functions](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference.html) are supported in GoFormation:

- [x] [Fn::Base64](intrinsics/fnbase64.go)
- [x] [Fn::FindInMap](intrinsics/fnfindinmap.go)
- [x] [Fn::Join](intrinsics/fnjoin.go)
- [x] [Fn::Select](intrinsics/fnselect.go)
- [x] [Fn::Split](intrinsics/fnsplit.go)
- [x] [Fn::Sub](intrinsics/fnsub.go)
- [x] [Ref](intrinsics/ref.go) 
- [ ] Fn::And      
- [ ] Fn::Equals  
- [ ] Fn::If     
- [ ] Fn::Not      
- [ ] Fn::Or       
- [ ] Fn::GetAtt   
- [ ] Fn::GetAZs   
- [ ] Fn::ImportValue

Any unsupported intrinsic functions will return `nil`.

#### Resolving References (Ref)

The intrinsic 'Ref' function as implemented will resolve all of the [pseudo parameters](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-ref.html) such as `AWS::AccountId` with their default value as listed on [the bottom of this page](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-ref.html).

If a reference is not a pseudo parameter, GoFormation will try to resolve it within the AWS CloudFormation template. **Currently, this implementation only searches for `Parameters` with a name that matches the ref, and returns the `Default` if it has one.**

#### Warning: YAML short form intrinsic functions (e.g. !Sub)

While this library supports both JSON and YAML AWS CloudFormation templates, it cannot handle short form intrinsic functions in YAML templates (e.g. `!Sub`). 

We will be adding support soon, however we need to patch Go's YAML library as it doesn't currently support tags.

If you use a short form intrinsic function today, you'll either get the unresolved value (if the recieving field is a string field), or the template will fail to parse (if it's recieving field is a non-string field).

## Contributing

Contributions and feedback are welcome! Proposals and pull requests will be considered and responded to. For more information, see the [CONTRIBUTING](CONTRIBUTING.md) file.
