package main

import (
	"bytes"
	"fmt"
	"os"
	"strings"
	"text/template"
)

// Property represents an AWS CloudFormation resource property
type Property struct {

	// Documentation - A link to the AWS CloudFormation User Guide that provides information about the property.
	Documentation string `json:"Documentation"`

	// DuplicatesAllowed - If the value of the Type field is List, indicates whether AWS CloudFormation allows duplicate values.
	// If the value is true, AWS CloudFormation ignores duplicate values. If the value is false,
	// AWS CloudFormation returns an error if you submit duplicate values.
	DuplicatesAllowed bool `json:"DuplicatesAllowed"`

	// ItemType - If the value of the Type field is List or Map, indicates the type of list or map if they contain
	// non-primitive types. Otherwise, this field is omitted. For lists or maps that contain primitive
	// types, the PrimitiveItemType property indicates the valid value type.
	//
	// A subproperty name is a valid item type. For example, if the type value is List and the item type
	//  value is PortMapping, you can specify a list of port mapping properties.
	ItemType string `json:"ItemType"`

	// PrimitiveItemType - If the value of the Type field is List or Map, indicates the type of list or map
	// if they contain primitive types. Otherwise, this field is omitted. For lists or maps that contain
	// non-primitive types, the ItemType property indicates the valid value type.
	// The valid primitive types for lists and maps are String, Long, Integer, Double, Boolean, or Timestamp.
	// For example, if the type value is List and the item type value is String, you can specify a list of strings
	// for the property. If the type value is Map and the item type value is Boolean, you can specify a string
	// to Boolean mapping for the property.
	PrimitiveItemType string `json:"PrimitiveItemType"`

	// PrimitiveType - For primitive values, the valid primitive type for the property. A primitive type is a
	// basic data type for resource property values.
	// The valid primitive types are String, Long, Integer, Double, Boolean, Timestamp or Json.
	// If valid values are a non-primitive type, this field is omitted and the Type field indicates the valid value type.
	PrimitiveType string `json:"PrimitiveType"`

	// Required indicates whether the property is required.
	Required bool `json:"Required"`

	// Type - For non-primitive types, valid values for the property. The valid types are a subproperty name,
	// List or Map. If valid values are a primitive type, this field is omitted and the PrimitiveType field
	// indicates the valid value type. A list is a comma-separated list of values. A map is a set of key-value pairs,
	// where the keys are always strings. The value type for lists and maps are indicated by the ItemType
	// or PrimitiveItemType field.
	Type string `json:"Type"`

	// UpdateType - During a stack update, the update behavior when you add, remove, or modify the property.
	// AWS CloudFormation replaces the resource when you change Immutable properties. AWS CloudFormation doesn't
	// replace the resource when you change mutable properties. Conditional updates can be mutable or immutable,
	// depending on, for example, which other properties you updated. For more information, see the relevant
	// resource type documentation.
	UpdateType string `json:"UpdateType"`

	// Types - if a property can be different types, they will be listed here
	PrimitiveTypes     []string `json:"PrimitiveTypes"`
	PrimitiveItemTypes []string `json:"PrimitiveItemTypes"`
	ItemTypes          []string `json:"ItemTypes"`
	Types              []string `json:"Types"`
}

// Schema returns a JSON Schema for the resource (as a string)
func (p Property) Schema(name, parent string) string {

	// Open the schema template and setup a counter function that will
	// available in the template to be used to detect when trailing commas
	// are required in the JSON when looping through maps
	tmpl, err := template.New("schema-property.template").Funcs(template.FuncMap{
		"counter": counter,
	}).ParseFiles("generate/templates/schema-property.template")

	var buf bytes.Buffer
	parentpaths := strings.Split(parent, ".")

	templateData := struct {
		Name     string
		Parent   string
		Property Property
	}{
		Name:     name,
		Parent:   parentpaths[0],
		Property: p,
	}

	// Execute the template, writing it to the buffer
	err = tmpl.Execute(&buf, templateData)
	if err != nil {
		fmt.Printf("Error: Failed to generate property %s\n%s\n", name, err)
		os.Exit(1)
	}

	return buf.String()

}

// IsPolymorphic checks whether a property can be multiple different types
func (p Property) IsPolymorphic() bool {
	return len(p.PrimitiveTypes) > 0 || len(p.PrimitiveItemTypes) > 0 || len(p.PrimitiveItemTypes) > 0 || len(p.ItemTypes) > 0 || len(p.Types) > 0
}

// IsPrimitive checks whether a property is a primitive type
func (p Property) IsPrimitive() bool {
	return p.PrimitiveType != ""
}

// IsMap checks whether a property should be a map (map[string]...)
func (p Property) IsMap() bool {
	return p.Type == "Map"
}

// IsMapOfPrimitives checks whether a map contains primitive values
func (p Property) IsMapOfPrimitives() bool {
	return p.IsMap() && p.PrimitiveItemType != ""
}

// IsList checks whether a property should be a list ([]...)
func (p Property) IsList() bool {
	return p.Type == "List"
}

// IsListOfPrimitives checks whether a list containers primitive values
func (p Property) IsListOfPrimitives() bool {
	return p.IsList() && p.PrimitiveItemType != ""
}

// IsCustomType checks wither a property is a custom type
func (p Property) IsCustomType() bool {
	return p.PrimitiveType == "" && p.ItemType == "" && p.PrimitiveItemType == ""
}

// GoType returns the correct type for this property
// within a Go struct. For example, []string or map[string]AWSLambdaFunction_VpcConfig
func (p Property) GoType(basename string) string {

	if p.IsPolymorphic() {

		types := append([]string{}, p.PrimitiveTypes...)
		types = append(types, p.Types...)

		for _, t := range p.PrimitiveItemTypes {
			types = append(types, "ListOf"+t)
		}

		for _, t := range p.ItemTypes {
			types = append(types, "ListOf"+t)
		}

		name := basename + "_" + strings.Join(types, "Or")
		generatePolymorphicProperty(name, p)
		return name

	}

	if p.IsMap() {

		if p.IsMapOfPrimitives() {
			return "map[string]" + convertTypeToGo(p.PrimitiveItemType)
		}

		if p.ItemType == "Tag" {
			return "map[string]Tag"
		}

		return "map[string]" + basename + "_" + p.ItemType

	}

	if p.IsList() {

		if p.IsListOfPrimitives() {
			return "[]" + convertTypeToGo(p.PrimitiveItemType)
		}

		if p.ItemType == "Tag" {
			return "[]Tag"
		}

		return "[]" + basename + "_" + p.ItemType

	}

	if p.IsCustomType() {
		return basename + "_" + p.Type
	}

	// Must be a primitive value
	return convertTypeToGo(p.PrimitiveType)

}

// GetJSONPrimitiveType returns the correct primitive property type for a JSON Schema.
// If the property is a list/map, then it will return the type of the items.
func (p Property) GetJSONPrimitiveType() string {

	if p.IsPrimitive() {
		return convertTypeToJSON(p.PrimitiveType)
	}

	if p.IsMap() && p.IsMapOfPrimitives() {
		return convertTypeToJSON(p.PrimitiveItemType)
	}

	if p.IsList() && p.IsListOfPrimitives() {
		return convertTypeToJSON(p.PrimitiveItemType)
	}

	return "unknown"

}

func convertTypeToGo(pt string) string {
	switch pt {
	case "String":
		return "string"
	case "Long":
		return "int64"
	case "Integer":
		return "int"
	case "Double":
		return "float64"
	case "Boolean":
		return "bool"
	case "Timestamp":
		return "string"
	case "Json":
		return "interface{}"
	default:
		return pt
	}
}

func convertTypeToJSON(name string) string {
	switch name {
	case "String":
		return "string"
	case "Long":
		return "number"
	case "Integer":
		return "number"
	case "Double":
		return "number"
	case "Boolean":
		return "boolean"
	case "Timestamp":
		return "string"
	case "Json":
		return "object"
	default:
		return name
	}
}
