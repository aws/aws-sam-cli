# AWS GoFormation (Alpha)

GoFormation is a CloudFormation parser written in Golang. By using GoFormation in your project, you can parse CloudFormation templates and use their information in your app.

- [GoFormation (Alpha)](#aws-goformation-alpha)
	- [Installation](#installation)
	- [Usage](#usage)
		- [Opening the template file](#opening-the-template-file)
		- [Parsing template contents](#parsing-template-contents)
		- [Using the parsed template](#using-the-parsed-template)
		- [Resources](#resources)
			- [Template-centric interfaces](#template-centric-interfaces)
				- [Template](#template)
				- [Resource](#resource)
				- [Property](#property)
			- [Resource-centric interfaces](#resource-centric-interfaces)
				- [AWSServerlessFunction](#awsserverlessfunction)

## Installation

The easiest way to get GoFormation is through `go get`:

```
go get github.com/awslabs/aws-goformation
```

This will get you a fresh copy of AWS GoFormation directly from the repository, into your `$GOPATH`.

## Usage

For using GoFormation you just need to reference in your Go app, whenever you want to use it:

### Opening the template file

If you want GoFormation to manage the opening of the file before the parsing, the way to proceed is `goformation.Open("template-file.yaml")`:

```
// my_file.go
package main

import "github.com/awslabs/goformation"

func main() {
	template, errors, logs := goformation.Open("my-template.yaml")
	// Do something with your template parsed.
}
```

### Parsing template contents

If you rather use directly the contents of a template, then you should use `goformation.Parse("template-contents")`:

```
// my_file.go
package main

import "github.com/awslabs/goformation"

func main() {
	var textTemplate []byte = ... // Get your template's contents somewhere
	template, errors, logs := goformation.Parse(textTemplate)
	// Do something with your template parsed.
}
```

### Using the parsed template

Once your template is parsed, you can easily get the resources parsed, to do any action with them - _NOTE: Currently, AWS GoFormation only supports `AWS::Serverless::Function` resources._ -:

```
// my_file.go
package main

import (
	"github.com/awslabs/goformation",
	. "github.com/awslabs/goformation/resources"
)

func main() {
	template, errors, logs := goformation.Open("my-template.yaml")
	// Verify there's no errors on parsing

	resources := template.Resources() // Get All resources
	functions := template.GetResourcesByType("AWS::Serverless::Function") // Get only Serverless Functions

	// Iterate over the parsed functions
	for fnName, fnData := range functions {	
		fnParsed := fnData.(AWSServerlessFunction)

		// Get function data
		fnRuntime := fnParsed.Runtime()
		log.Printf("Runtime: %s", fnRuntime) // Outputs the function's runtime
	}
}
```

### Resources

The inner package `resource` contains exported interfaces that are useful for working with GoFormation-parsed templates:

#### Template-centric interfaces

These interfaces give you means to access your template's information, and reflects the same structure that you can see on your JSON/YAML template. Once the template is parsed, these interfaces would also return computed outputs, by linking resources via Intrinsic Functions:

##### Template

```
type Template interface {
	Version() string
	Transform() []string
	Parameters() map[string]Parameter
	Resources() map[string]Resource
	Outputs() map[string]Output

	GetResourcesByType(resourceType string) map[string]Resource
}
```

##### Resource

```
type Resource interface {
	Type() string
	Properties() map[string]Property
	ReturnValues() map[string]string
}
```

##### Property

type Property interface {
	Value() interface{}
	Original() interface{}
	HasFn() bool
}

#### Resource-centric interfaces

While the template-specific interfaces give you enough capabilities for accessing all of your template's information, the way it does is somewhat generic, and sometimes you'd rather do some actions with certain specific kinds of resources. The resource-centric interfaces give you access to the resource's capabilities directly.

Once your template is parsed, you can access any resource type with the function `template.GetResourcesByType("AWS::Resource::Name")`. During [post processing](#post-processing), every interpretable resource is casted to be compliant to its own interface. A simple type assertion would hence give you the capabilities described here:

##### AWSServerlessFunction

`AWSServerlessFunction` is the resource that defines a `AWS::Serverless::Function` resources. Once you make the type assertion, you can leverage all of its parameters:

```
// Interface definition
type AWSServerlessFunction interface {
	Handler() string
	Runtime() string
	CodeURI() AWSCommonStringOrS3Location
	FunctionName() string
	Description() string
	MemorySize() int
	Timeout() int
	Role() interface{}
	Policies() []string
	EnvironmentVariables() map[string]string
	Endpoints() ([]AWSServerlessFunctionEndpoint, error)
}
```

_EXAMPLE:_

```
...
// Use an AWSServerlessFunction
functions := template.GetResourcesByType("AWS::Serverless::Function")
for _, fn := range functions {
	function := fn.(AWSServerlessFunction)
}
...

```