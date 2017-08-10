package goformation

import (
	"regexp"
	"strings"

	. "github.com/awslabs/goformation/resources"
	"github.com/awslabs/goformation/util"
)

var globalValues = map[string]string{
	"AWS::Region":           "xx-mylaptop-1",
	"AWS::AccountId":        "1234567890",
	"AWS::NotificationARNs": "",
	"AWS::NoValue":          "",
	"AWS::StackId":          "arn:aws:cloudformation:us-west-2:123456789012:stack/teststack/51af3dc0-da77-11e4-872e-1234567db123",
	"AWS::StackName":        "My local stack",
}

var fnRegex = `Fn::(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub|Ref)`

// PostProcess gets a template and a set of parsed resources, and resolves its references
func postProcess(input Template) (Template, error) {
	util.LogDebug(-1, "PostProcessing", "Started post-processing template")

	resultTemplate := processedFromScaffolded(input)
	util.LogDebug(-1, "PostProcessing", "Iterating over resources")
	processedResources := make(map[string]Resource)
	allResources := resultTemplate.Resources()
	factory := GetResourceFactory()
	for name, res := range allResources {
		util.LogDebug(-1, "PostProcessing", "Processing resource %s", name)
		resourceType := res.Type()
		resourceDefinition := factory.GetResourceByType(resourceType)
		if resourceDefinition == nil {
			util.LogWarning(-1, "Post Processing", "Ignoring resource type %s as it's not supported", resourceType)
			continue
		}

		util.LogDebug(-1, "PostProcessing", "Processing intrinsic functions")
		error := resolveIntrinsicFunctions(res, allResources)
		if error != nil {
			return nil, error
		}

		resourceClass, error := resourceDefinition.ClassConstructor(res)
		if error != nil {
			return nil, error
		}
		processedResources[name] = resourceClass
	}

	resultTemplate._resources = processedResources

	return resultTemplate, nil
}

func processedFromScaffolded(input Template) *processedTemplate {
	resultTemplate := &processedTemplate{
		_version:    input.Version(),
		_transform:  input.Transform(),
		_parameters: input.Parameters(),
		_resources:  make(map[string]Resource),
		_outputs:    input.Outputs(),
	}

	for key, res := range input.Resources() {
		procResource := &processedResource{
			_properties: make(map[string]Property),
			_type:       res.Type(),
		}

		for p, prop := range res.Properties() {
			if prop == nil {
				continue
			}

			procResource._properties[p] = &processedProperty{
				_original: prop.Original(),
				_value:    nil,
			}
		}

		resultTemplate._resources[key] = procResource
	}

	return resultTemplate
}

type processedTemplate struct {
	_version    string
	_transform  []string
	_parameters map[string]Parameter
	_resources  map[string]Resource
	_outputs    map[string]Output
}

func (t *processedTemplate) Version() string {
	return t._version
}
func (t *processedTemplate) Transform() []string {
	return t._transform
}
func (t *processedTemplate) Parameters() map[string]Parameter {
	return t._parameters
}
func (t *processedTemplate) Resources() map[string]Resource {
	return t._resources
}
func (t *processedTemplate) Outputs() map[string]Output {
	return t._outputs
}

func (t *processedTemplate) GetResourcesByType(resourceType string) map[string]Resource {
	matchingResources := make(map[string]Resource)
	for key, res := range t._resources {
		if res.Type() == resourceType {
			matchingResources[key] = res
		}
	}
	return matchingResources
}

type processedResource struct {
	_type       string
	_properties map[string]Property
	_lineNumber int
}

func (r *processedResource) Type() string {
	return r._type
}

func (r *processedResource) Properties() map[string]Property {
	props := make(map[string]Property)
	for key, value := range r._properties {
		setPropertyKey(props, key, value)
	}
	return props
}

func (r *processedResource) ReturnValues() map[string]string {
	return nil
}

type processedProperty struct {
	_original  interface{}
	_value     interface{}
	lineNumber int
}

func (p *processedProperty) Value() interface{} {
	return p._value
}
func (p *processedProperty) Original() interface{} {
	return p._original
}
func (p *processedProperty) HasFn() bool {
	return false
}

func resolveIntrinsicFunctions(res Resource, resources map[string]Resource) error {
	util.LogDebug(-1, "PostProcessing", "Started intrinsic function resolution")
	properties := res.Properties()
	parsedProperties := lookupObject(properties, resources)
	parsedResource := res.(*processedResource)
	parsedResource._properties = parsedProperties
	util.LogDebug(-1, "PostProcessing", "Intrinsic function resolution finished")

	return nil
}

func resolveValue(input string, resources map[string]Resource) string {
	var globalValueRegex = `AWS::`
	globalMatch, error := regexp.Match(globalValueRegex, []byte(input))
	if error != nil {

	} else if globalMatch {
		output, outputSet := globalValues[input]
		if !outputSet {
			util.LogError(-1, "PostProcessing", "The value %s does not exist", input)
		} else {
			return output
		}
	} else {
		parsedInput := strings.Split(input, `.`)
		matchingResource, resourceExists := resources[parsedInput[0]]
		if !resourceExists {
			return ""
		}

		var returnParam string
		// Is it a Ref or an Att?
		if len(parsedInput) == 1 {
			returnParam = "Ref"
		} else {
			returnParam = parsedInput[1]
		}

		returnValues := matchingResource.ReturnValues()
		output, outputOk := returnValues[returnParam]
		if !outputOk {
			util.LogError(-1, "PostProcessing", "Output %s does not exist for resource %s", returnParam, parsedInput[0])
			return ""
		}

		return output
	}

	return ""
}

func fnBase64(value string, resources map[string]Resource) string {
	return ""
}

func fnFindInMap(value string, resources map[string]Resource) string {
	return ""
}

func fnGetAZs(value string, resources map[string]Resource) string {
	return ""
}

func fnImportValue(value string, resources map[string]Resource) string {
	return ""
}

func fnJoin(value []interface{}, resources map[string]Resource) string {
	valueLen := len(value)
	if valueLen != 2 {
		util.LogError(-1, "PostProcessing", "Fn::Join array needs two elements: delimiter and list")
	} else {
		delimiter, delimiterStringOk := value[0].(string)
		listInterface, listArrayOk := value[1].([]interface{})
		if !delimiterStringOk || !listArrayOk {
			util.LogError(-1, "PostProcessing", "The delimiter or the list of values provided for Fn::Join is incorrect")
		} else {
			list := make([]string, len(listInterface))
			for _, listValue := range listInterface {
				valueString, valueStringOk := listValue.(string)
				if !valueStringOk {
					util.LogError(-1, "PostProcessing", "One of the values of the Fn::Join list is not a String")
				} else {
					list = append(list, valueString)
				}
			}

			result := strings.Join(list, delimiter)
			return result
		}
	}

	return ""
}

func fnSelect(value string, resources map[string]Resource) string {
	return ""
}

func fnSplit(value string, resources map[string]Resource) string {
	return ""
}

func fnGetAtt(value string, resources map[string]Resource) string {
	output := resolveValue(value, resources)
	return output
}

func fnSub(value interface{}, resources map[string]Resource, inlineParameters map[string]interface{}) string {

	var substitutionString string
	var resolutionVariables map[string]interface{}

	// Sub 1: Inline string
	if valueString, ok := value.(string); ok {
		substitutionString = valueString
	} else if valueArray, ok := value.([]interface{}); ok {
		substitutionString = valueArray[0].(string)
		resolutionVariables = valueArray[1].(map[string]interface{})
	} else {
		util.LogError(-1, "PostProcessing", "Source object for Sub is of an unsopported type")
		return ""
	}

	// First resolve the resolution variables
	var resolvedVariables = map[string]interface{}{}
	for key, variable := range resolutionVariables {
		realValue := resolveValue(variable.(string), resources)
		if realValue != "" {
			resolvedVariables[key] = realValue
		} else {
			resolvedVariables[key] = variable
		}
	}

	// Identify variables in substitution text
	var varInTextStr = `\$\{([a-zA-Z0-9_:]+)\}`
	varInTextRegex := regexp.MustCompile(varInTextStr)
	occurrences := varInTextRegex.FindAllString(substitutionString, -1)
	for _, occurrence := range occurrences {
		occurrenceMatches := varInTextRegex.FindStringSubmatch(occurrence)
		parameterName := occurrenceMatches[1]

		var keyResolved = false
		var value string
		if inlineParameters != nil {
			inlineParameter, inlineParameterExists := inlineParameters[parameterName]
			if inlineParameterExists {
				var valueString bool
				value, valueString = inlineParameter.(string)
				if !valueString {
					util.LogError(-1, "PostProcessing", "Value from inline resolution must be a String")
					return ""
				}

				keyResolved = true
			}
		}

		if !keyResolved {
			value = resolveValue(parameterName, resources)
			if value == "" {
				util.LogWarning(-1, "PostProcessing", "The value %s does not resolve.", parameterName)
			}
		}

		substitutionString = strings.Replace(substitutionString, `${`+parameterName+`}`, value, 1)
	}

	return substitutionString
}

func complexFnSub(valueArray []interface{}, resources map[string]Resource) string {
	valueLen := len(valueArray)
	if valueLen != 2 {
		util.LogError(-1, "PostProcessing", "Wrong number of attributes %d for Fn::Sub %s", valueLen, valueArray)
	} else {
		valueSentence, valueSentenceString := valueArray[0].(string)
		valueAttributes, valueAttributesMap := valueArray[1].(map[interface{}]interface{})
		if !valueSentenceString {
			util.LogError(-1, "PostProcessing", "First parameter for Fn::Sub must be a String.")
		} else {
			if !valueAttributesMap {
				util.LogError(-1, "PostProcessing", "The second parameter for Fn::Sub must be a map, %s:%s", valueSentence, valueArray[1])
			} else {
				// TODO Convert attributes to properties
				attributesProps := make(map[string]Property)
				for attrKey, attrValue := range valueAttributes {
					attributesProps[attrKey.(string)] = &processedProperty{
						_value: attrValue,
					}
				}
				lookupObject(attributesProps, resources)

				mapString := make(map[string]interface{})
				for mapKey, mapValue := range valueAttributes {
					mapKeyString, mapKeyStringOk := mapKey.(string)
					if !mapKeyStringOk {
						util.LogError(-1, "PostProcessing", "One of the Fn::Sub attribute keys is not a string, %s", mapKey)
					} else {
						mapString[mapKeyString] = mapValue
					}
				}

				// Now let's resolve the content
				return fnSub(valueSentence, resources, mapString)
			}
		}
	}

	return ""
}

func fnRef(value string, resources map[string]Resource) string {
	realValue := resolveValue(value, resources)
	if realValue == "" {
		util.LogError(-1, "PostProcessing", "Ref not resolving")
	}

	return realValue
}

func resolveInline(fn string, value interface{}, resources map[string]Resource) (string, error) {
	var realValue string
	var error error

	valueArray, valueArrayOk := value.([]interface{})
	if valueArrayOk {
		resolvedValue := lookupArray(valueArray, resources)
		if _, resolvedValueArrayOk := resolvedValue.([]interface{}); !resolvedValueArrayOk {
			value = resolvedValue.(string)
		}
	}

	switch fn {
	case "Base64":
		fallthrough
	case "FindInMap":
		fallthrough
	case "GetAZs":
		fallthrough
	case "ImportValue":
		fallthrough
	case "Select":
		fallthrough
	case "Split":
		realValue = "Intrinsic function " + fn + ""
	case "Join":
		valueArray, arrayOk := value.([]interface{})
		if !arrayOk {
			util.LogError(-1, "PostProcessing", "Fn::Join function received wrong input `%s`", value)
		} else {
			realValue = fnJoin(valueArray, resources)
		}
	case "GetAtt":
		realValue = fnGetAtt(value.(string), resources)
	case "Sub":
		subAttrs, inlineComplex := value.([]interface{})
		if inlineComplex {
			subString := subAttrs[0]
			functionAttributes := subAttrs[1]
			// Create complexSub data
			subData := []interface{}{
				subString,
				functionAttributes,
			}

			realValue = complexFnSub(subData, resources)
		} else {
			realValue = fnSub(value, resources, nil)
		}
	case "Ref":
		realValue = fnRef(value.(string), resources)
	}

	return realValue, error
}

func lookupArray(source []interface{}, resources map[string]Resource) interface{} {
	// First, look through the array looking for inner intrinsic
	for key, value := range source {
		valueArray, valueArrayOk := value.([]interface{})
		if valueArrayOk {
			resolvedValue := lookupArray(valueArray, resources)
			source[key] = resolvedValue
		}
	}

	// Now look if there's an intrinsic in this array
	if len(source) > 0 {
		var objectKey, objectKeyString = source[0].(string)
		if objectKeyString {
			// Find inline Intrinsic Functions:
			hasInlineFn, error := regexp.Match(fnRegex, []byte(objectKey))
			if error != nil {
				util.LogError(-1, "PostProcessing", "%s", error.Error())
			} else if hasInlineFn {
				regex := regexp.MustCompile(fnRegex)
				occurrence := regex.FindString(objectKey)

				fnMatches := regex.FindStringSubmatch(occurrence)
				fn := fnMatches[1]
				fnValue := source[1]

				// Verify if value contains inner inline intrinsic
				fnValueArray, fnValueArrayOk := fnValue.([]interface{})
				if fnValueArrayOk {
					fnValue = lookupArray(fnValueArray, resources)
				}

				var sourceValue interface{}
				if len(source) > 2 {
					valueArray := make([]interface{}, 2)

					fnAttrs := source[2]
					valueArray = append(valueArray, fnValue)
					valueArray = append(valueArray, fnAttrs)

					sourceValue = valueArray
				} else {
					sourceValue = fnValue
				}

				resolvedValue, resolutionError := resolveInline(fn, sourceValue, resources)
				if resolutionError != nil {
					util.LogError(-1, "PostProcessing", "Resolution error: %s", resolutionError.Error())
				} else {
					return resolvedValue
				}
			} else {
				return source
			}
		}
	}

	return nil
}

func lookupObject(source map[string]Property, resources map[string]Resource) map[string]Property {
	util.LogDebug(-1, "PostProcessing", "Looking up properties")

	resultProperties := make(map[string]Property)
	for key, prop := range source {
		util.LogDebug(-1, "PostProcessing", "Looking through key %s", key)
		value := prop.Original()

		realValue := recursiveObjectLookup(key, value, resources)
		resultProperties[key] = realValue
	}

	return resultProperties
}

func recursiveObjectLookup(key string, value interface{}, resources map[string]Resource) *processedProperty {
	realValue := &processedProperty{
		_original: value,
		_value:    value,
	}

	// Is it a map?
	if obj, isObj := value.(map[string]Property); isObj {
		util.LogDebug(-1, "PostProcessing", "Complex object found. Iterating...")
		returnValue := lookupObject(obj, resources)
		if returnValue != nil {
			realValue._value = returnValue
		}
	}

	if obj, isObj := value.(map[interface{}]interface{}); isObj {
		util.LogDebug(-1, "PostProcessing", "Complex object found. Iterating...")
		objProps := make(map[string]Property)
		for keyObj, valueObj := range obj {
			if valueProp, valuePropOk := valueObj.(Property); valuePropOk {
				valuePropValue := valueProp.Value()
				if valuePropValueProp, valuePropValuePropOk := valuePropValue.(Property); valuePropValuePropOk {
					objProps[keyObj.(string)] = valuePropValueProp
				} else {
					objProps[keyObj.(string)] = valueProp
				}
			} else {
				resolvedValue := detectIntrinsicFunctionsInObject(keyObj.(string), valueObj, resources)
				var valueToAssign interface{}
				if resolvedValue == nil {
					// Nothing to do if value is null, resolution haven't been made
					valueToAssign = value
				} else if resolvedValueProp, resolvedValuePropOk := resolvedValue.(*processedProperty); resolvedValuePropOk {
					// Returned value is a property, so get the value.
					valueToAssign = resolvedValueProp._value
				} else {
					valueToAssign = resolvedValue
				}

				obj[keyObj] = valueToAssign
			}
		}

		realValue._value = obj

		if len(objProps) > 0 {
			returnValue := lookupObject(objProps, resources)
			if returnValue != nil {
				realValue._value = returnValue
			}
		}
	}

	// Look for functions in the value
	if valueArray, isArray := value.([]interface{}); isArray {
		util.LogDebug(-1, "PostProcessing", "Array found, iterating")
		resolvedValue := lookupArray(valueArray, resources)
		if valueStr, valueStrOk := resolvedValue.(string); valueStrOk {
			realValue._value = valueStr
		}
	}

	return realValue
}

func detectIntrinsicFunctionsInObject(key string, value interface{}, resources map[string]Resource) interface{} {

	keymatch, error := regexp.Match(fnRegex, []byte(key))
	if error != nil {
		util.LogError(-1, "PostProcessing", "%s", error)
	} else if keymatch || key == "Ref" {
		switch key {
		case "Fn::Base64":
			fallthrough
		case "Fn::FindInMap":
			fallthrough
		case "Fn::GetAZs":
			fallthrough
		case "Fn::Select":
			fallthrough
		case "Fn::Split":
			util.LogWarning(-1, "PostProcessing", "Intrinsic function %s ", key)
		case "Fn::ImportValue":
			return ""
		case "Fn::Join":
			valueArray, arrayOk := value.([]interface{})
			if !arrayOk {
				util.LogError(-1, "PostProcessing", "Fn::Join function received wrong input `%s`", value)
			} else {
				return fnJoin(valueArray, resources)
			}
		case "Fn::GetAtt":
			valueArray, arrayOk := value.([]interface{})
			if !arrayOk {
				util.LogError(-1, "PostProcessing", "Fn::GetAtt function received wrong input `%s`", value)
			} else {
				valueLen := len(valueArray)
				if valueLen != 2 {
					util.LogError(-1, "PostProcessing", "Wrong number of attributes %d for Fn::GetAtt %s", valueLen, value)
				} else {
					valueResource, valueResourceString := valueArray[0].(string)
					valueAttribute, valueAttributeString := valueArray[1].(string)

					if !valueResourceString || !valueAttributeString {
						util.LogError(-1, "PostProcessing", "Attributes for Fn::GetAtt must be Strings.")
					} else {
						compiledValue := valueResource + `.` + valueAttribute
						return fnGetAtt(compiledValue, resources)
					}
				}
			}
		case "Fn::Sub":
			valueArray, arrayOk := value.([]interface{})
			if !arrayOk {
				// It's not an array. Maybe it's a string?
				valueString, valueStringOk := value.(string)
				if !valueStringOk {
					util.LogError(-1, "PostProcessing", "Fn::Sub needs either an array or a String.")
				} else {
					return fnSub(valueString, resources, nil)
				}
			} else {
				return complexFnSub(valueArray, resources)
			}
		case "Ref":
			valueString, valueStringOk := value.(string)
			if !valueStringOk {
				util.LogError(-1, "PostProcessing", "Ref function requires a string.")
			} else {
				return resolveValue(valueString, resources)
			}
		}
	} else {
		// innerValue := &processedProperty{
		// 	_original: value,
		// 	_value:    nil,
		// }
		innerValue := recursiveObjectLookup(key, value, resources)
		return innerValue
	}

	return nil
}
