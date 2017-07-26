# GoFormation

GoFormation is a CloudFormation template parser, written in Golang. By using CloudFormation you can interprete your templates, and use its contents in local development phases, or anywhere you can imagine. 

## Installation
`TODO`

## Usage
For using GoFormation standalone, the easiest way is through the cli:
```
goformation parse --template MY_TEMPLATE_FILE.yaml

-- (OUTPUT) --
GoFormation parsing template file MY_TEMPLATE_FILE.yaml
Template parsed successfully
Your template contains the following:
* MY_TEMPLATE_FILE.yaml 
* * 19 Parameters (0 Used) // TBD
* * 18 Resources (12 Parsed)
* * 6 Outputs (0 Generated) // TBD
```

In this example you can see how GoFormation went through your resources analyzing them, and generated a text output for you. While this serves no extra purpose, it allows you to validate the syntax and correctness of your template.

### GoFormation library
Probably the most useful way to leverage GoFormation, is by including it as a module in your application. By including GoFormation, you will have out-of-the-box CloudFormation parsing capabilities, that you can easily extend with your custom code.

If you want to install GoFormation in your project, follow this steps.

#### Install GoFormation in your Go environment
```
go get github.com/awslabs/goformation
```

This will get you a fresh copy of GoFormation, ready to include in your app.

#### Import GoFormation in your project
Include this as an import in your Go file:
```
// my_app.go
import "github.com/awslabs/goformation"
```

#### Parse a template from file
```
// my_app.go
...
template, logs, error := goformation.Open("MY_TEMPLATE.yaml")
// Process template
```

#### Parse template contents
```
// my_app.go
...
my_template = []byte // Should be read before
template, logs, error := goformation.Parse(my_template)
// Process template
```

### Resources package
Along with the parsing capabilities, GoFormation publishes a set of interfaces that you can leverage for reading your template’s information. All these interfaces are found at “github.com/awslabs/goformation/resources”. 

#### Template
A `Template` is the Golang representation of a CloudFormation template. It contains the following structure:

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

#### Parameter
A `Parameter` represents an input for the stack, specified in the template. Parameters have this signature:

```
type Parameter interface {
	AllowedPattern() string
	AllowedValues() []string
	ConstraintDescription() string
	Default() string
	Description() string
	MaxLength() string
	MaxValue() string
	MinLength() string
	MinValue() string
	NoEcho() string
	Type() string
}
```

#### Resource
A `Resource` contains the information about a template’s resource.

```
type Resource interface {
	Type() string
	Properties() map[string]Property
	ReturnValues() map[string]string
}
```

#### Property
A `Property` is a property configuration for a resource. It has this structure.

```
type Property interface {
	Value() interface{}
	Original() interface{}
	HasFn() bool
}
```

#### Output
An output is value that gets exported from the template’s interpretation. It obeys to this signature:

```
type Output interface {
	Description() string
	Value() string
	Export() ExportParam
}
```

#### ExportParam
`ExportParam` is the ultimate export information for a template’s output. It contains only the method `Name()`, that returns a `string` with the name of the attribute.

#### Resource-specific interfaces
Along with the aforementioned template-centric interfaces, GoFormation also exports other interfaces that represent specific resources within your template, in a more resource-centric way. This allows you to use the resources from your templates easier.

Currently, GoFormation only supports resources of type `AWS::Serverless::Function`, as it was built to enable the parsing capabilities to [SAM CLI](https://github.com/awslabs/aws-sam-cli). We are working to include all CloudFormation resources now. 

##### AWS::Serverless::Function
This Resource type represents a Lambda Function, defined through [SAM](https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md). Once the template is parsed and all the values are set, GoFormation outputs this interface for all functions found:

```
type AWSServerlessFunction interface {
	Handler() string
	Runtime() string
	CodeURI() AWSCommonS3Location
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

`TODO` Inner resources

### Intrinsic Function support

GoFormation includes Intrinsic Function support, for the following intrinsic functions:

- [ ] Fn::Base64.
- [ ] Condition Functions.
- [ ] Fn::FindInMap.
- [x] Fn::GetAtt.
- [ ] Fn::GetAZs.
- [x] Fn::ImportValue.
- [x] Fn::Join.
- [ ] Fn::Select.
- [ ] Fn::Split.
- [x] Fn::Sub.
- [x] Ref.

If an intrinsic function represents an output for a resource not supported by GoFormation, such intrinsic function will be resolved as an empty string. Non-supported intrinsic functions also evaluate as empty strings. 

## Error specification

`TODO`

## Log Information

`TODO`

## Contribute

`TODO`