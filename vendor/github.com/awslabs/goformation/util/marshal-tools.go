package util

import (
	"gopkg.in/yaml.v2"
)

// ParsePrimitive parses a primitive value from the template
func ParsePrimitive(source interface{}) interface{} {
	if v, ok := source.(string); ok {
		return v
	} else if v, ok := source.(bool); ok {
		return v
	} else if v, ok := source.(int); ok {
		return v
	}
	return ""
}

// ParseComplex parses a complex value from the template
func ParseComplex(source interface{}, destination interface{}) {

	enc, err := yaml.Marshal(source)
	if err != nil {
		LogError(-1, "UNDEFINED", "%s", err)
	}
	if err := yaml.Unmarshal(enc, destination); err != nil {
		LogError(-1, "UNDEFINED", "%s", err)
	}
}

// GetValueType returns the data type of a value given
func GetValueType(value interface{}) string {
	switch value.(type) {
	case string:
		return "string"
	case int:
		return "int"
	case int64:
		return "int64"
	case float32:
		return "float32"
	case float64:
		return "float64"
	case bool:
		return "bool"
	case []string:
		return "[]string"
	case []int:
		return "[]int"
	case []int64:
		return "[]int64"
	case []float32:
		return "[]float32"
	case []float64:
		return "[]float64"
	case []bool:
		return "[]bool"
	default:
		return "Unknown"
	}
}
