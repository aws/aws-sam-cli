package goformation

import (
	"errors"
	"fmt"

	. "github.com/awslabs/goformation/resources"
	"github.com/awslabs/goformation/util"
)

var (
	ErrUnableToReadResourceLineNumbers = errors.New("Failed to read the resources line numbers. This usually means that the template contains invalid indentation. Please check it and try again")
	ErrNoResourcesSectionDefined       = errors.New("The template does not contain a 'Resources' section")
)

// TODO Document
func scaffold(input Template) (Template, []error) {
	var error = []error{}

	util.LogDebug(-1, "Scaffolding", "Started template scaffolding")
	resultUnmarshalledTemplate := input.(*unmarshalledTemplate)

	util.LogDebug(-1, "Scaffolding", "Transforming template types")
	resultTemplate := scaffoldFromUnmarshalled(resultUnmarshalledTemplate)

	util.LogDebug(-1, "Scaffolding", "Fetching line numbers")
	resultLineNumbers := resultUnmarshalledTemplate._lineNumbers
	mappedLineNumbers, err := readResourceLineNumbers(resultLineNumbers)
	if err != nil {
		util.LogError(-1, "Scaffolding", "Failed to read line number information")
		error = append(error, err)
		return nil, error
	}

	util.LogDebug(-1, "Scaffolding", "Line numbers correctly.")
	resourcesLinesRaw, resourcesLinesOk := mappedLineNumbers["Resources"]
	if !resourcesLinesOk {
		err := errors.New("Template does not contain a Resources section (line: 0; col: 0)")
		util.LogError(-1, "Scaffolding", err.Error())
		error = append(error, err)
		return nil, error
	}

	resourcesLines := resourcesLinesRaw.(map[string]interface{})
	util.LogDebug(-1, "Scaffolding", "Line analysis obtained %d resources", len(resourcesLines))

	resultingResources := make(map[string]Resource)
	allResources := resultTemplate.Resources()
	for name, resourceTemplate := range allResources {
		linesForResourceRaw, linesForResourceOk := resourcesLines[name]
		if !linesForResourceOk {
			util.LogError(-1, "Scaffolding", "Unable to retrieve resource line information")
			error = append(error, ErrUnableToReadResourceLineNumbers)
			return nil, error
		}

		linesForResource := linesForResourceRaw.(map[string]interface{})
		util.LogDebug(-1, "Scaffolding", "Fetched lines for resource.")

		parsedResource, error := scaffoldResource(name, resourceTemplate, linesForResource)
		if len(error) > 0 {
			util.LogError(-1, "Scaffolding", "Error scaffolding resource %s", name)
			return nil, error
		}

		if parsedResource == nil {
			continue
		}

		resultingResources[name] = parsedResource
	}

	resultTemplate._resources = resultingResources

	return &resultTemplate, nil
}

func readResourceLineNumbers(obj LineDictionary) (map[string]interface{}, error) {
	objValue := obj.Value()
	objKey := obj.Key()

	util.LogDebug(-1, "Scaffolding", "Reading lineDictionary key %s", objKey)
	children := obj.Children()
	ret := make(map[string]interface{})

	util.LogDebug(-1, "Scaffolding", "Object has %d children", len(children))
	for _, child := range children {
		key := child.Key()
		value := child.Value()

		util.LogDebug(-1, "Scaffolding", "Getting child %s", value)

		parsedChild, error := readResourceLineNumbers(child)
		if error != nil {
			util.LogError(-1, "Scaffolding", "Failed getting child %s of lineDictionary %s", value, objValue)
			return nil, error
		}

		if key != "" {
			// TODO Contemplate Array cases.
			ret[key] = parsedChild
		} else {
			ret[value] = parsedChild
		}
	}

	ret["ROOT"] = obj

	return ret, nil
}

func scaffoldResource(name string, resourceTemplate Resource, lines map[string]interface{}) (Resource, []error) {
	resourceType := resourceTemplate.Type()
	rootResourceLinesRaw, rootResourceLinesOk := lines["ROOT"]
	if !rootResourceLinesOk {
		util.LogError(-1, "Scaffolding", "Lines for resource %s are missing", name)
		return nil, []error{ErrUnableToReadResourceLineNumbers}
	}
	rootResourceLines := rootResourceLinesRaw.(LineDictionary)

	typeLinesRaw, typeLinesRawOk := lines["Type"]
	if !typeLinesRawOk {
		msg := fmt.Sprintf("Resource %s has no Type set (line: %d; col: %d)", name, rootResourceLines.Line(), rootResourceLines.Level())
		util.LogError(rootResourceLines.Line(), "Scaffolding", msg)
		return nil, []error{errors.New(msg)}
	}
	typeLinesRoot := typeLinesRaw.(map[string]interface{})
	typeLines := typeLinesRoot["ROOT"].(LineDictionary)

	propertiesLinesRaw, propertiesLinesRawOk := lines["Properties"]
	propertiesLinesRoot := map[string]interface{}{}
	if !propertiesLinesRawOk {
		// The resource is missing a Properties section, but that's ok.
		propertiesLinesRoot = map[string]interface{}{}
	} else {
		propertiesLinesRoot = propertiesLinesRaw.(map[string]interface{})
	}

	util.LogDebug(rootResourceLines.Line(), "Scaffolding", "Resource %s (line %d) has type %s", name, rootResourceLines.Line(), resourceType)
	factory := GetResourceFactory()
	resourceDefinition := factory.GetResourceByType(resourceType)

	if resourceDefinition == nil {
		util.LogWarning(typeLines.Line(), "Scaffolding", "The resource %s is not supported (line: %d; col: %d)", name, typeLines.Line(), typeLines.Level())
		return nil, nil
	}

	util.LogDebug(-1, "Scaffolding", "Fetched resouce definition for %s", resourceType)
	resourceResourceDefinitionBase, err := resourceDefinition.Resource()
	if err != nil {
		return nil, []error{err}
	}

	util.LogDebug(-1, "Scaffolding", "Scaffolding resource %s", name)
	resourceInterface := resourceResourceDefinitionBase.(EditableResource)
	parsedResource, error := resourceInterface.Scaffold(name, resourceTemplate, propertiesLinesRoot)
	if error != nil && len(error) > 0 {
		return nil, error
	}

	util.LogDebug(-1, "Scaffolding", "Resource %s scaffolded", name)

	return parsedResource, nil
}

func scaffoldFromUnmarshalled(input Template) scaffoldedTemplate {
	template := scaffoldedTemplate{
		_version:    input.Version(),
		_transform:  input.Transform(),
		_parameters: input.Parameters(),
		_outputs:    input.Outputs(),
		_resources:  make(map[string]Resource),
	}

	for key, res := range input.Resources() {
		scaffResource := &scaffoldedResource{
			_properties: make(map[string]*scaffoldedProperty),
			_type:       res.Type(),
		}

		for p, prop := range res.Properties() {
			if prop == nil {
				continue
			}

			scaffResource._properties[p] = &scaffoldedProperty{
				_value: prop.Original(),
			}
		}

		template._resources[key] = scaffResource
	}

	return template
}

type scaffoldedTemplate struct {
	_version     string
	_transform   []string
	_parameters  map[string]Parameter
	_resources   map[string]Resource
	_outputs     map[string]Output
	_lineNumbers LineDictionary
}

func (t *scaffoldedTemplate) Version() string {
	return t._version
}
func (t *scaffoldedTemplate) Transform() []string {
	return t._transform
}
func (t *scaffoldedTemplate) Parameters() map[string]Parameter {
	return t._parameters
}
func (t *scaffoldedTemplate) Resources() map[string]Resource {
	return t._resources
}
func (t *scaffoldedTemplate) Outputs() map[string]Output {
	return t._outputs
}

func (t *scaffoldedTemplate) GetResourcesByType(resourceType string) map[string]Resource {
	return nil
}

type scaffoldedResource struct {
	_type       string
	_properties map[string]*scaffoldedProperty
	_lineNumber int
}

func (r *scaffoldedResource) Type() string {
	return r._type
}

func (r *scaffoldedResource) Properties() map[string]Property {
	props := make(map[string]Property)
	for key, value := range r._properties {
		setPropertyKey(props, key, value)
	}
	return props
}

func (r *scaffoldedResource) ReturnValues() map[string]string {
	return nil
}

type scaffoldedProperty struct {
	_value     interface{}
	lineNumber int
}

func (p *scaffoldedProperty) Value() interface{} {
	return nil
}
func (p *scaffoldedProperty) Original() interface{} {
	return p._value
}
func (p *scaffoldedProperty) HasFn() bool {
	return false
}
