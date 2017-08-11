package resources

import (
	"regexp"

	"github.com/awslabs/goformation/util"
	"github.com/pkg/errors"
)

// TODO Document
type EditableResource interface {
	Type() string
	Properties() map[string]Property
	ReturnValues() map[string]string

	Scaffold(name string, data Resource, lines map[string]interface{}) (Resource, []error)
}

// ErrInvalidResourceType Invalid type assigned to resource
var ErrInvalidResourceType = errors.New("The given resource type is invalid")

// ErrResourceInvalidPropertyNumber Invalid number of properties on a resource definition
var ErrResourceInvalidPropertyNumber = errors.New("Every resource must have at least one property")

// ErrUnknownAttributeDefinition Invalid number of properties on a resource definition
var ErrUnknownAttributeDefinition = errors.New("Every resource must have at least one property")

// ErrInvalidResourceDefinition Invalid definition received for a resource
var ErrInvalidResourceDefinition = errors.New("Resource definition invalid")

// ErrScaffoldUndefinedType The given data does not define a resource type
var ErrScaffoldUndefinedType = errors.New("The given data does not define a resource type")

// ErrScaffoldUndefinedProperties The given data does not define any property
var ErrScaffoldUndefinedProperties = errors.New("The given data does not define any property")

// ErrScaffoldInvalidResourceType Invalid or ungiven type when scaffolding a resource
var ErrScaffoldInvalidResourceType = errors.New("Invalid type given for scaffolding a resource")

// ErrScaffoldRequiredValueNotSet Required value not set for resource
var ErrScaffoldRequiredValueNotSet = errors.New("Required value not set for resource")

// newResource Create a new resource with the information given
func newResource(_type string, properties map[string]*property, returnValues map[string]func(Resource) interface{}) (Resource, error) {

	var error error

	error = validateResourceType(_type)
	if error != nil {
		return nil, error
	}

	// Verify that there are properties present
	var hasProperties = false
	for range properties {
		hasProperties = true
	}
	if !hasProperties {
		error = ErrResourceInvalidPropertyNumber
		return nil, error
	}

	resource := &resource{
		_type:         _type,
		_properties:   properties,
		_returnValues: returnValues,
	}

	return resource, error
}

// DefineResource helps quickly defining resources with a raw multi-map
func DefineResource(config map[string]interface{}) (Resource, error) {
	util.LogDebug(-1, "Resources", "Starting Resource definition")

	var resource Resource
	var error error

	var _type string
	var properties map[string]*property
	var returnValues map[string]func(Resource) interface{}

	for key, attributes := range config {

		switch key {
		case "Type":
			_type = attributes.(string)
			util.LogDebug(-1, "Resources", "Resource has type %s", _type)
		case "Properties":
			util.LogDebug(-1, "Resources", "Defining resource's Properties")
			properties = nil
			unparsedProperties := attributes.(map[string]map[string]interface{})
			properties = make(map[string]*property)
			for key, prop := range unparsedProperties {
				util.LogDebug(-1, "Resources", "Defining property %s", key)
				propInterface, error := DefineProperty(prop)
				if error != nil {
					util.LogError(-1, "Resources", "Error defining property %s", key)
					return nil, error
				}

				properties[key] = propInterface.(*property)
			}

		case "ReturnValues":
			util.LogDebug(-1, "Resources", "Defining Resource's ReturnValues")
			returnValues = attributes.(map[string]func(Resource) interface{})
		default:
			util.LogError(-1, "Resources", "The Resource has an undefined attribute %s", key)
			error = ErrUnknownAttributeDefinition
			return nil, error
		}
	}

	if properties == nil || returnValues == nil {
		error = ErrInvalidResourceDefinition
		return nil, error
	}

	resource, error = newResource(_type, properties, returnValues)
	if error != nil {
		return nil, error
	}

	util.LogDebug(-1, "Resources", "Resource %s defined correctly", _type)
	return resource, error
}

// Begin resource definition

type resource struct {
	_type         string
	_properties   map[string]*property
	_returnValues map[string]func(Resource) interface{}
	_lines        map[string]interface{}
}

func (r *resource) Type() string {
	return r._type
}

func (r *resource) Properties() map[string]Property {
	props := make(map[string]Property)
	for key, value := range r._properties {
		props[key] = value
	}

	return props
}

func (r *resource) ReturnValues() map[string]string {
	return nil
}

// End resource definition

func validateResourceType(_type string) error {
	switch _type {
	case "AWS::Serverless::Function":
		fallthrough
	case "AWS::Serverless::Api":
		fallthrough
	case "AWS::Serverless::SimpleTable":
		return nil
	}

	return ErrInvalidResourceType
}

var lineExistenceRegex = regexp.MustCompile(`\(line:\s(\d+);\scol:\s(\d+)\)`)

// Scaffold constructs a new Resource with the given data
func (r *resource) Scaffold(name string, data Resource, lines map[string]interface{}) (Resource, []error) {
	var error = []error{}

	resourceType := data.Type()

	util.LogDebug(-1, "Resources", "Starting scaffolding for resource %s", resourceType)

	// Verify that a type is given
	if resourceType == "" {
		util.LogError(-1, "Resources", "Resource type for resource not given.")
		error = append(error, ErrScaffoldUndefinedType)
		return nil, error
	}

	// Verify that the given type matches with definition's
	if resourceType != r._type {
		util.LogError(-1, "Resources", "The resource type given - i.e. %s - is different from the resource's - %s", resourceType, r._type)
		error = append(error, ErrScaffoldInvalidResourceType)
		return nil, error
	}

	util.LogDebug(-1, "Resources", "Creating resource")
	result := &resource{
		_type:       resourceType,
		_properties: make(map[string]*property),
		_lines:      lines,
	}

	propLinesRoot := lines["ROOT"].(LineDictionary)

	// Verify that a properties object is given
	util.LogDebug(propLinesRoot.Line(), "Resources", "Scaffolding resource's properties (line %d)", propLinesRoot.Line())
	dataProperties := data.Properties()
	if dataProperties == nil || len(dataProperties) == 0 {
		util.LogError(propLinesRoot.Line(), "Resources", "Properties are not set for resource %s", name)
	}

	// Iterate over definition's properties
	scaffoldedProperties := make(map[string]*property)
	for propName, propDefinition := range r._properties {
		util.LogDebug(-1, "Resources", "Scaffolding property %s", propName)

		var propertyLines map[string]interface{}
		propertyLinesRaw, propertyLinesRawOk := lines[propName]
		if !propertyLinesRawOk {
			util.LogDebug(-1, "Resources", "Unable to find line information for property %s", propName)
		} else {
			propertyLines = propertyLinesRaw.(map[string]interface{})
		}

		prop, err := propDefinition.Scaffold(propName, dataProperties[propName], data, propertyLines)
		if err != nil {
			util.LogError(propLinesRoot.Line(), "Resources", "There was an error scaffolding property %s", propName)

			errorWrapperString := `Resource "%s", property "%s"`
			previousError := err.Error()

			var wrappedError = errors.Wrapf(err, errorWrapperString, name, propName)
			if !lineExistenceRegex.MatchString(previousError) {
				errorWrapperString += `: ### (line: %d; col: %d)`
				wrappedError = errors.Wrapf(err, errorWrapperString, name, propName, propLinesRoot.Line(), propLinesRoot.Level())
			}

			error = append(error, wrappedError)
			scaffoldedProperties[propName] = nil
		} else {
			util.LogDebug(-1, "Resources", "Root Property %s finished scaffolding", propName)
			scaffoldedProperties[propName] = prop.(*property)
		}
	}

	result._properties = scaffoldedProperties

	// Compile return values
	returnValues := make(map[string]string)
	for returnKey, returnFn := range r._returnValues {
		fnResult := returnFn(result)
		if fnResult == nil {
			util.LogError(-1, "Resources", "The return value %s returns nil", returnKey)
			continue
		} else if _, ok := fnResult.(string); !ok {
			util.LogError(-1, "Resources", "The return value %s does not return a string", returnKey)
			continue
		}

		resultString := fnResult.(string)
		returnValues[returnKey] = resultString
	}

	result._returnValues = r._returnValues

	return result, error
}
