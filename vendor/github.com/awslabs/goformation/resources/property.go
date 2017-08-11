package resources

import (
	"regexp"
	"strings"

	"github.com/pkg/errors"

	"github.com/awslabs/goformation/util"
)

// ErrUnsetPropertyType The property type has been not set
var ErrUnsetPropertyType = errors.New("Every property needs to have at least one data type")

// ErrInvalidPropertyTypeObject The `type` object given is invalid
var ErrInvalidPropertyTypeObject = errors.New("The types definition for a Property must be either a String or an Array of strings")

// ErrInvalidPropertyType One of the types given to the property is invalid
var ErrInvalidPropertyType = errors.New("One of the given types is invalid")

// ErrInvalidPropertyDefaultValueType The default value given for the property has an invalidType
var ErrInvalidPropertyDefaultValueType = errors.New("The default value set for the property is not a valid type")

// ErrInvalidPropertyValueType The value given to the property has an invalid type
var ErrInvalidPropertyValueType = errors.New("The type of the value set for the property is incorrect")

// ErrResourceNotSetForReferencedProperty Referenced properties need to have a Resource associated
var ErrResourceNotSetForReferencedProperty = errors.New("Referenced types need to have a resource. Use `newReferenceProperty` method instead")

// ErrPropertyDefinitionUnsetType Property definition without types
var ErrPropertyDefinitionUnsetType = errors.New("When defining a property you must indicate its type")

// ErrTreatingASimpleVariableAsComplex Treating a primitive value as an object
var ErrTreatingASimpleVariableAsComplex = errors.New("Treating a primitive value as an object")

// ErrPropertyDidntPassSpecificValidation Occurs when the property-specific validations don't validate the property value
var ErrPropertyDidntPassSpecificValidation = errors.New("Unable to validate the property against its specific validators")

// newProperty Creates a new Property with the information given in the template
func newProperty(types interface{}, required bool, defaultValue interface{}, validator func(source interface{}) (bool, string)) (Property, error) {
	var prop Property

	realTypes, error := validatePropertyTypes(types, required, defaultValue)
	if error != nil {
		util.LogError(-1, "Properties", "Error validating Property types.")
		return nil, error
	}

	if validType, _ := valueTypeIsValid(&realTypes, defaultValue); !validType {
		error = ErrInvalidPropertyDefaultValueType
		return nil, error
	}

	// Reject Referenced types
	if realTypes[0] == "Resource" || realTypes[0] == "[]Resource" {
		util.LogError(-1, "Properties", "Rejected using simple property definition for %s", realTypes)
		error = ErrResourceNotSetForReferencedProperty
		return nil, error
	}

	prop = &property{
		_types:     realTypes,
		_required:  required,
		_default:   defaultValue,
		_validator: validator,
	}

	return prop, error
}

// newReferenceProperty Creates a property that references other resource
func newReferenceProperty(types interface{}, required bool, res map[string]*property, validator func(source interface{}) (bool, string)) (Property, error) {

	realTypes, error := validatePropertyTypes(types, required, nil)

	if error != nil {
		return nil, error
	}

	prop := property{
		_types:     realTypes,
		_required:  required,
		_resource:  res,
		_validator: validator,
	}

	return &prop, nil
}

// DefineProperty Defines a new property with the data given
func DefineProperty(config map[string]interface{}) (Property, error) {
	util.LogDebug(-1, "Properties", "Starting Property definition")
	var prop Property
	var error error

	var propTypes interface{}
	var propRequired = false
	var propDefault interface{}
	var propValidator func(interface{}) (bool, string)
	var propReference map[string]*property

	util.LogDebug(-1, "Properties", "Creating Property's attributes")
	isReference := false
	for key, attribute := range config {
		switch key {
		case "Types":
			propTypes = attribute
		case "Required":
			propRequired = attribute.(bool)
		case "Default":
			propDefault = attribute
		case "Resource":
			isReference = true
			ref, error := parseInnerProperties(attribute.(map[string]map[string]interface{}))
			if error != nil {
				return nil, error
			}
			propReference = ref
		case "Validator":
			propValidator = attribute.(func(interface{}) (bool, string))
		}
	}

	if propTypes == nil {
		error = ErrPropertyDefinitionUnsetType
	} else if isReference {
		prop, error = newReferenceProperty(propTypes, propRequired, propReference, propValidator)
	} else {
		prop, error = newProperty(propTypes, propRequired, propDefault, propValidator)
	}

	if error != nil {
		return nil, error
	}

	return prop, nil
}

func parseInnerProperties(source map[string]map[string]interface{}) (map[string]*property, error) {
	util.LogDebug(-1, "Properties", "Defining Property's inner Properties")
	result := make(map[string]*property)
	for key, value := range source {
		util.LogDebug(-1, "Properties", "Defining inner property %s", key)
		prop, error := DefineProperty(value)
		if error != nil {
			util.LogError(-1, "Properties", "Failed to define property %s", key)
			return nil, error
		}

		util.LogDebug(-1, "Properties", "Storing inner Property")
		result[key] = prop.(*property)
	}

	return result, nil
}

// Begin property definition

type property struct {
	_types     []string
	_required  bool
	_default   interface{}
	_validator func(source interface{}) (bool, string)
	_resource  map[string]*property
	_value     interface{}
}

func (p *property) HasFn() bool {
	return false
}
func (p *property) Original() interface{} {
	return p._value
}
func (p *property) Scaffold(name string, propValue Property, source Resource, lines map[string]interface{}) (Property, error) {
	var error error

	// Verify if data is not set for this property
	if propValue == nil {
		util.LogDebug(-1, "Properties", "Property has no assigned value")

		util.LogDebug(-1, "Properties", "Trying to apply default value")
		rawDefaultValue := p._default
		if rawDefaultValue != nil {
			var valueToSet interface{}

			// The default value is a function?
			if defaultValueFn, defaultIsFn := rawDefaultValue.(func(Resource) interface{}); defaultIsFn {
				util.LogDebug(-1, "Properties", "The default value is a function")
				tempValue := defaultValueFn(source)
				valueToSet = tempValue
			} else {
				valueToSet = rawDefaultValue
			}
			util.LogDebug(-1, "Properties", "The default value to set is %s", valueToSet)

			currentProp, error := doScaffold(valueToSet, p, source, lines)
			if error != nil {
				return nil, error
			}

			return currentProp, nil
		}

		if p._required {
			util.LogError(-1, "Properties", "The property is required, but no value has been set.")
			error = ErrScaffoldRequiredValueNotSet
			return nil, error
		}

		// Create a nil property
		util.LogDebug(-1, "Properties", "Value not set. Creating empty Property")
		prop := &property{
			_value: nil,
		}

		return prop, nil

	}

	var propLines LineDictionary
	rootLines, rootLinesOk := lines["ROOT"]
	if rootLinesOk {
		propLines = rootLines.(LineDictionary)
	} else {
		propLines = &lineDictionary{
			_line: -1,
		}
	}

	value := propValue.Original()
	util.LogDebug(-1, "Properties", "Property has the template value set to %s (line: %d; col: %d)", value, propLines.Line(), propLines.Level())

	currentProp, error := doScaffold(value, p, source, lines)
	if error != nil {
		return nil, error
	}

	return currentProp, nil
}
func (p *property) Value() interface{} {
	return p._value
}

func doScaffold(value interface{}, prop *property, resource Resource, lines map[string]interface{}) (*property, error) {
	var propLines LineDictionary
	rootLines, rootLinesOk := lines["ROOT"]
	if rootLinesOk {
		propLines = rootLines.(LineDictionary)
	} else {
		propLines = &lineDictionary{
			_line: -1,
		}
	}

	util.LogDebug(-1, "Properties", "Verifying that property's value has correct type")
	validType, dataType := valueTypeIsValid(&prop._types, value)
	if !validType {
		// TODO Set line
		error := errors.Wrapf(ErrInvalidPropertyValueType, `Expecting "%s", got "%s" (line: %d; col: %d)`, strings.Join(prop._types, " or "), util.GetValueType(value), propLines.Line(), propLines.Level())
		return nil, error
	}

	if dataType == "" {
		util.LogDebug(-1, "Properties", "The value validator could not determine the value's type")
	}

	var realValue interface{}
	switch dataType {
	case "map[string]Resource":
		fallthrough
	case "map[int]Resource":
		parsedValue, error := doScaffoldMap(value.(map[interface{}]interface{}), prop, resource, lines)
		if error != nil {
			return nil, error
		}

		realValue = parsedValue
	case "Resource":
		parsedValue, error := doScaffoldResource(value, prop, resource, lines)
		if error != nil {
			return nil, error
		}

		realValue = parsedValue
	case "[]Resource":
		parsedValue, error := doScaffoldResourceArray(value.([]interface{}), prop, resource, lines)
		if error != nil {
			return nil, error
		}

		realValue = parsedValue
	case "infn":
		realValue = value
	case "string":
		fallthrough
	case "int":
		fallthrough
	case "int64":
		fallthrough
	case "float32":
		fallthrough
	case "float64":
		fallthrough
	case "bool":
		fallthrough
	case "[]string":
		fallthrough
	case "[]int":
		fallthrough
	case "[]int64":
		fallthrough
	case "[]float32":
		fallthrough
	case "[]float64":
		fallthrough
	case "[]bool":
		fallthrough
	case "map[string]string":
		fallthrough
	case "map[int]string":
		fallthrough
	default:
		util.LogDebug(-1, "Properties", "Value assigned plain because type is %s", dataType)
		realValue = value
	}

	// Validate property against defined validations
	propValidator := prop._validator
	if propValidator != nil {
		propValidation, validationError := propValidator(realValue)
		if !propValidation {
			util.LogError(propLines.Line(), "Properties", "The value %s has not pass property-specific validations", realValue)
			wrappedError := errors.Wrapf(ErrPropertyDidntPassSpecificValidation, validationError+` (line: %d; col: %d)`, propLines.Line(), propLines.Level())
			return nil, wrappedError
		}
	}

	util.LogDebug(-1, "Properties", "Wrapping scaffolded property")
	propValue := &property{
		_value: realValue,
	}

	return propValue, nil
}

func doScaffoldResourceArray(value []interface{}, prop *property, resource Resource, lines map[string]interface{}) ([]interface{}, error) {
	util.LogDebug(-1, "Properties", "Property is a Resource array. Iterating")
	ret := make([]interface{}, len(value))

	// Create resource property
	resourceProperty := &property{
		_types:    []string{"Resource"},
		_default:  prop._default,
		_required: true,
		_resource: prop._resource,
	}

	for key, res := range value {
		result, error := doScaffold(res, resourceProperty, resource, lines)
		if error != nil {
			return nil, error
		}

		ret[key] = result
	}

	return ret, nil
}

func doScaffoldMap(value map[interface{}]interface{}, prop *property, resource Resource, lines map[string]interface{}) (map[interface{}]interface{}, error) {
	util.LogDebug(-1, "Properties", "Property is a Resource map. Iterating")
	ret := make(map[interface{}]interface{}, len(value))

	// Create resource property
	resourceProperty := &property{
		_types:    []string{"Resource"},
		_default:  prop._default,
		_required: true,
		_resource: prop._resource,
	}

	for key, res := range value {
		var mapPropertyLines map[string]interface{}
		rootInnerPropLines, rootInnerPropLinesOk := lines[key.(string)]
		if rootInnerPropLinesOk {
			innerPropLinesMap, innerPropLinesMapOk := rootInnerPropLines.(map[string]interface{})
			if innerPropLinesMapOk {
				mapPropertyLines = innerPropLinesMap
			}
		}

		util.LogDebug(-1, "Properties", "Processing Property %s", key)
		tmpResult, error := doScaffold(res, resourceProperty, resource, mapPropertyLines)
		if error != nil {
			return nil, error
		}

		ret[key] = tmpResult
	}

	return ret, nil
}

func doScaffoldResource(value interface{}, prop *property, resource Resource, lines map[string]interface{}) (interface{}, error) {
	var propLines LineDictionary
	rootLines, rootLinesOk := lines["ROOT"]
	if rootLinesOk {
		propLines = rootLines.(LineDictionary)
	} else {
		propLines = &lineDictionary{
			_line: -1,
		}
	}

	complexValue, complexValueOk := value.(map[interface{}]interface{})
	if !complexValueOk {
		util.LogError(propLines.Line(), "Properties", "Property is set as complex, but no complex value given. %s", value)
		return nil, errors.Wrapf(ErrTreatingASimpleVariableAsComplex, `Property expected type "Resource", got "%s" (line: %d; col: %d)`, util.GetValueType(value), propLines.Line(), propLines.Level())
	}

	propertiesProperties := prop._resource
	propertyValues := make(map[string]Property)
	for propKey, propProp := range propertiesProperties {
		util.LogDebug(-1, "Properties", "Scaffolding inner property %s", propKey)
		var keyFace interface{} = propKey
		valueKey := complexValue[keyFace]
		util.LogDebug(-1, "Properties", "Value set for inner Property %s: %s", propKey, valueKey)

		if propProp._required && valueKey == nil {
			util.LogError(propLines.Line(), "Properties", "Inner property has no value, yet it's required.")
			return nil, errors.Wrapf(ErrScaffoldRequiredValueNotSet, "Inner property %s is required (line: %d; col: %d)", propKey, propLines.Line(), propLines.Level())
		}

		propValue, error := doScaffold(valueKey, propProp, resource, lines)
		if error != nil {
			util.LogError(-1, "Properties", "Failed to scaffold inner Property %s", propKey)
			return nil, error
		}

		propertyValues[propKey] = propValue
	}

	return propertyValues, nil
}

// End property definition

func typesAreValid(types *[]string) bool {
	for _, t := range *types {
		var isPrimitive = false
		var isArray = false
		var isMap = false
		var isComplexMap = false
		var isRef = false

		switch t {
		case "string":
			fallthrough
		case "int":
			fallthrough
		case "int64":
			fallthrough
		case "float32":
			fallthrough
		case "float64":
			fallthrough
		case "bool":
			isPrimitive = true

		case "[]string":
			fallthrough
		case "[]int":
			fallthrough
		case "[]int64":
			fallthrough
		case "[]float32":
			fallthrough
		case "[]float64":
			fallthrough
		case "[]bool":
			isArray = true
		case "map[string]Resource":
			fallthrough
		case "map[int]Resource":
			isComplexMap = true
			fallthrough
		case "map[string]string":
			fallthrough
		case "map[int]string":
			isMap = true
		case "Resource":
			fallthrough
		case "[]Resource":
			isRef = true
		}

		if !(isPrimitive || isArray || isRef || isMap || isComplexMap) {
			return false
		}
	}
	return true
}

func valueTypeIsValid(types *[]string, value interface{}) (bool, string) {

	if _, ok := value.(func(Resource) interface{}); ok {
		util.LogDebug(-1, "Properties", "Property's value is set via a function")
		return true, ""
	}

	if value == nil {
		util.LogDebug(-1, "Properties", "Value is null. Nothing to validate")
		return true, ""
	}

	// If the value has an intrinsic function, then don't raise validation error
	regularIntrinsicFnRegex := regexp.MustCompile(`(Fn::(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub)|Ref)`)
	valueComplex, valueComplexOk := value.(map[interface{}]interface{})
	if valueComplexOk {
		for cKey := range valueComplex {
			var ccKey string
			if cKeyPtr, cKeyPtrOk := cKey.(*string); cKeyPtrOk {
				ccKey = *cKeyPtr
			} else {
				ccKey = cKey.(string)
			}

			if regularIntrinsicFnRegex.MatchString(ccKey) {
				return true, "infn"
			}
		}
	} else if valueArray, valueArrayOk := value.([]interface{}); valueArrayOk {
		for _, cValue := range valueArray {
			var valueStr string
			if cValueStr, cValueStrOk := cValue.(string); cValueStrOk {
				valueStr = cValueStr
			} else if cValueStr, cValueStrOk := cValue.(*string); cValueStrOk {
				valueStr = *cValueStr
			}

			if regularIntrinsicFnRegex.MatchString(valueStr) {
				return true, "string"
			}
		}
	} else if valueStr, valueStrOk := value.(string); valueStrOk {
		if regularIntrinsicFnRegex.MatchString(valueStr) {
			return true, "string"
		}
	}

	validationResults := make([]bool, len(*types))

	var dataType = ""
	for index, t := range *types {
		util.LogDebug(-1, "Properties", "Validating type %s", t)
		validationResults[index] = true
		switch t {
		case "string":
			_, ok := value.(string)
			if !ok {
				validationResults[index] = false
			}
		case "int":
			_, ok := value.(int)
			if !ok {
				validationResults[index] = false
			}
		case "int64":
			_, ok := value.(int64)
			if !ok {
				validationResults[index] = false
			}
		case "float32":
			_, ok := value.(float32)
			if !ok {
				validationResults[index] = false
			}
		case "float64":
			_, ok := value.(float64)
			if !ok {
				validationResults[index] = false
			}
		case "bool":
			_, ok := value.(bool)
			if !ok {
				validationResults[index] = false
			}
		case "[]string":
			_, ok1 := value.([]string)
			if !ok1 {
				_, ok2 := value.([]interface{})
				if !ok2 {
					validationResults[index] = false
				}
			}
		case "[]int":
			_, ok := value.([]int)
			if !ok {
				validationResults[index] = false
			}
		case "[]int64":
			_, ok := value.([]int64)
			if !ok {
				validationResults[index] = false
			}
		case "[]float32":
			_, ok := value.([]float32)
			if !ok {
				validationResults[index] = false
			}
		case "[]float64":
			_, ok := value.([]float64)
			if !ok {
				validationResults[index] = false
			}
		case "[]bool":
			_, ok := value.([]bool)
			if !ok {
				validationResults[index] = false
			}

		case "Resource":
			_, ok := value.(map[interface{}]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "Resource"
			}
		case "[]Resource":
			_, ok := value.([]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "[]Resource"
			}
		case "map[string]string":
			_, ok := value.(map[interface{}]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "map[string]string"
			}
		case "map[int]string":
			_, ok := value.(map[interface{}]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "map[int]string"
			}
		case "map[string]Resource":
			_, ok := value.(map[interface{}]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "map[string]Resource"
			}
		case "map[int]Resource":
			_, ok := value.(map[interface{}]interface{})
			if !ok || !valueComplexOk {
				validationResults[index] = false
			} else {
				dataType = "map[int]Resource"
			}
		}
	}

	util.LogDebug(-1, "Properties", "Convoluting global validity")
	for _, v := range validationResults {
		if v {
			util.LogDebug(-1, "Properties", "Found a valid type. Value is valid")
			return true, dataType
		}
	}

	util.LogError(-1, "Properties", "There's no valid type for matching value %s", value)
	return false, ""
}

func validatePropertyTypes(types interface{}, required bool, defaultValue interface{}) ([]string, error) {
	var error error
	var realTypes []string

	if v, ok := types.(string); ok {
		realTypes = []string{v}
	} else if v, ok := types.([]string); ok {
		realTypes = v
	} else {
		error = ErrInvalidPropertyTypeObject
		return realTypes, error
	}

	if len(realTypes) == 0 {
		error = ErrUnsetPropertyType
	} else if !typesAreValid(&realTypes) {
		util.LogError(-1, "Properties", "Error types: %s", realTypes)
		error = ErrInvalidPropertyType
	}

	return realTypes, error
}
