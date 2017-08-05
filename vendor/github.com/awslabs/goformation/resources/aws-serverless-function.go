package resources

import (
	"github.com/awslabs/goformation/util"
)

// AWSServerlessFunction is a broad interface that allows us to pass around
// functions of any AWS SAM specification version, while keeping
// a common interface that they should all adhear to
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

// AWSServerlessFunctionEndpoint provides information on where a Serverless function
// should be mounted on an API (for example, the HTTP method and path)
type AWSServerlessFunctionEndpoint interface {
	Path() string
	Methods() []string
}

type awsServerlessFunction struct {
}

//
// ResourceDefinition interface
//

func (f *awsServerlessFunction) ResourceType() string {
	return awsServerlessFunctionResourceType()
}

func (f *awsServerlessFunction) Template(source interface{}) Resource {
	template := &functionTemplate{}
	util.ParseComplex(source, template)

	return template
}

var fnDef, fnDefErr = functionDefinition()

func (f *awsServerlessFunction) Resource() (Resource, error) {
	if fnDefErr != nil {
		return nil, fnDefErr
	}

	return fnDef, nil
}

func (f *awsServerlessFunction) ClassConstructor(input Resource) (Resource, error) {

	res, error := f.Scaffold(input, "")
	if error != nil {
		return nil, error
	}

	return res.(Resource), nil
}

//
// End ResourceDefinition interface
//

//
// Scaffoldable interface
//

// TODO Document
func (f *awsServerlessFunction) Scaffold(input Resource, propName string) (AWSServerlessFunction, error) {
	function := &functionTemplate{}
	function.Scaffold(input, "")

	return function, nil
}

//
// End Scaffoldable interface
//

func awsServerlessFunctionResourceType() string {
	return "AWS::Serverless::Function"
}

type functionTemplate struct {
	FHandler      string                                      `yaml:"Handler"`
	FRuntime      string                                      `yaml:"Runtime"`
	FCodeURI      *stringOrS3Location                         `yaml:"CodeUri"`
	FFunctionName string                                      `yaml:"FunctionName"`
	FDescription  string                                      `yaml:"Description"`
	FMemorySize   int                                         `yaml:"MemorySize"`
	FTimeout      int                                         `yaml:"Timeout"`
	FRole         interface{}                                 `yaml:"Role"`
	FPolicies     ListOrString                                `yaml:"Policies"`
	FEnvironment  map[string]string                           `yaml:"Environment"`
	FVpcConfig    interface{}                                 `yaml:"VpcConfig"`
	FEventSources map[string]AWSServerlessFunctionEventSource `yaml:"Events"`
	Resource
}

//
// Resource interface
//
func (f *functionTemplate) Type() string {
	return awsServerlessFunctionResourceType()
}

func (f *functionTemplate) Properties() map[string]Property {
	resource := f.Resource
	return resource.Properties()
}

func (f *functionTemplate) ReturnValues() map[string]string {
	resource := f.Resource
	return resource.ReturnValues()
}

//
// End Resource interface
//

//
// Scaffoldable interface
//

func (f *functionTemplate) Scaffold(input Resource, propName string) (Resource, error) {
	f.Resource = input

	resourceProperties := input.Properties()

	f.FDescription = safeProcessString(resourceProperties["Description"])
	f.FHandler = safeProcessString(resourceProperties["Handler"])
	f.FRuntime = safeProcessString(resourceProperties["Runtime"])
	f.FFunctionName = safeProcessString(resourceProperties["FunctionName"])
	f.FMemorySize = safeProcessInt(resourceProperties["MemorySize"])
	f.FTimeout = safeProcessInt(resourceProperties["Timeout"])
	f.FRole = safeProcessString(resourceProperties["Role"])
	f.FPolicies = safeProcessStringArray(resourceProperties["Policies"])

	envValue := resourceProperties["Environment"].Value()
	if envValue != nil {
		fEnvironmentObject, fEnvironmentObjectOk := envValue.(map[string]Property)
		if fEnvironmentObjectOk {
			f.FEnvironment = safeProcessStringMap(fEnvironmentObject["Variables"])
		} else {
			util.LogDebug(-1, "AWS::Serverless::Function", "The environment has a wrong type")
		}
	}

	f.FCodeURI = &stringOrS3Location{}
	f.FCodeURI.Scaffold(input, "CodeUri")
	f.FEventSources = scaffoldEventSourceMap(resourceProperties["Events"])

	// FVpcConfig = resourceProperties["VpcConfig"].Value()
	// FResource = resourceProperties["Resource"].Value()

	// TODO Finish this

	return nil, nil
}

//
// End Scaffoldable interface
//

//
// AWSServerlessFunction interface
//
func (f *functionTemplate) Handler() string {
	return f.FHandler
}

func (f *functionTemplate) Runtime() string {
	return f.FRuntime
}

func (f *functionTemplate) CodeURI() AWSCommonStringOrS3Location {
	return f.FCodeURI
}

func (f *functionTemplate) FunctionName() string {
	return f.FFunctionName
}

func (f *functionTemplate) Description() string {
	return f.FDescription
}

func (f *functionTemplate) MemorySize() int {
	return f.FMemorySize
}

func (f *functionTemplate) Timeout() int {
	return f.FTimeout
}
func (f *functionTemplate) Role() interface{} {
	return f.FRole
}

func (f *functionTemplate) Policies() []string {
	return f.FPolicies
}

func (f *functionTemplate) EnvironmentVariables() map[string]string {
	return f.FEnvironment
}

//
// End AWSServerlessFunction interface
//

func (f *functionTemplate) Endpoints() ([]AWSServerlessFunctionEndpoint, error) {

	var endpoints = []AWSServerlessFunctionEndpoint{}

	for _, es := range f.FEventSources {
		if es.Type() == "Api" {
			if esApi, esApiOk := es.(AWSServerlessFunctionAPIEventSource); esApiOk {
				endpoints = append(endpoints, esApi.(*apiEventSource))
			}
		}
	}

	return endpoints, nil

}

func functionDefinition() (Resource, error) {
	var resource Resource
	var error error

	config := map[string]interface{}{
		"Type": awsServerlessFunctionResourceType(),
		"Properties": map[string]map[string]interface{}{
			"Handler": map[string]interface{}{
				"Types":    "string",
				"Required": true,
				"Default":  "index.handler",
			},
			"Runtime": map[string]interface{}{
				"Types":    "string",
				"Required": true,
				"Validator": func(rawValue interface{}) (bool, string) {
					value := rawValue.(string)

					switch value {
					case "nodejs":
						fallthrough
					case "nodejs4.3":
						fallthrough
					case "nodejs6.10":
						fallthrough
					case "java8":
						fallthrough
					case "python2.7":
						fallthrough
					case "python3.6":
						fallthrough
					case "dotnetcore1.0":
						fallthrough
					case "nodejs4.3-edge":
						return true, ""
					}
					return false, `Invalid value ` + value + `. Valid values are "nodejs", "nodejs4.3", "nodejs6.10", "java8", "python2.7", "python3.6", "dotnetcore1.0", "nodejs4.3-edge"`
				},
			},
			"CodeUri": map[string]interface{}{
				"Types":    []string{"Resource", "string"},
				"Required": false,
				"Resource": map[string]map[string]interface{}{
					"Bucket": map[string]interface{}{
						"Types":    "string",
						"Required": true,
					},
					"Key": map[string]interface{}{
						"Types":    "string",
						"Required": true,
					},
					"Version": map[string]interface{}{
						"Types":    "int",
						"Required": false,
					},
				},
			},
			"FunctionName": map[string]interface{}{
				"Types": "string",
				"Default": func(fn Resource) interface{} {
					return "ABCD"
					// TODO Set Name based on LogicalId
				},
				"Validator": func(source interface{}) (bool, string) {
					// Otherwise
					var result = true

					return result, ""
				},
			},
			"Description": map[string]interface{}{
				"Types": "string",
			},
			"MemorySize": map[string]interface{}{
				"Types":   "int",
				"Default": 128,
			},
			"Timeout": map[string]interface{}{
				"Types":   "int",
				"Default": 3,
			},
			"Role": map[string]interface{}{
				"Types": "string",
			},
			"Policies": map[string]interface{}{
				"Types":    []string{"Resource", "[]Resource", "string", "[]string"},
				"Resource": map[string]map[string]interface{}{},
				// TODO Policies validation NOT implemented
			},
			"Environment": map[string]interface{}{
				"Types": "Resource",
				"Resource": map[string]map[string]interface{}{
					"Variables": map[string]interface{}{
						"Types": "map[string]string",
					},
				},
			},
			"VpcConfig": map[string]interface{}{
				"Types":    "Resource",
				"Resource": map[string]map[string]interface{}{},
				// TODO VPCConfig validation NOT implemented
			},
			"Events": map[string]interface{}{
				"Types": "map[string]Resource",
				"Resource": map[string]map[string]interface{}{
					"Type": map[string]interface{}{
						"Types": "string",
						"Validator": func(source interface{}) (bool, string) {
							// Otherwise
							var result = true

							return result, ""
						},
						"Required": true,
					},
					"Properties": map[string]interface{}{
						"Types":    "map[string]string",
						"Required": true,
					},
				},
				// TODO Events validation NOT implemented
			},
			"Tags": map[string]interface{}{
				"Types": "map[string]string",
			},
		},
		"ReturnValues": map[string]func(Resource) interface{}{
			"Ref": func(fn Resource) interface{} {
				fnProperties := fn.Properties()
				functionName := fnProperties["FunctionName"].Value().(string)
				return functionName
			},
			"Arn": func(fn Resource) interface{} {
				fnProperties := fn.Properties()
				functionName := fnProperties["FunctionName"].Value().(string)
				var arn = "arn:aws:lambda:region:account-id:function:" + functionName

				return arn
			},
		},
	}

	resource, error = DefineResource(config)
	if error != nil {
		return nil, error
	}

	return resource, nil
}
