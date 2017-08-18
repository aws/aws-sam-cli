package main

import (
	"bytes"
	"fmt"
	"os"
	"sort"
	"strings"
	"text/template"
)

// Resource represents an AWS CloudFormation resource such as AWS::EC2::Instance
type Resource struct {

	// Documentation is a link to the AWS CloudFormation User Guide for information about the resource.
	Documentation string `json:"Documentation"`

	// Properties are a list of property specifications for the resource. For details, see:
	// http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-resource-specification-format.html#cfn-resource-specification-format-propertytypes
	Properties map[string]Property
}

// Schema returns a JSON Schema for the resource (as a string)
func (r Resource) Schema(name string) string {

	// Open the schema template and setup a counter function that will
	// available in the template to be used to detect when trailing commas
	// are required in the JSON when looping through maps
	tmpl, err := template.New("schema-resource.template").Funcs(template.FuncMap{
		"counter": counter,
	}).ParseFiles("generate/templates/schema-resource.template")

	var buf bytes.Buffer

	templateData := struct {
		Name     string
		Resource Resource
	}{
		Name:     name,
		Resource: r,
	}

	// Execute the template, writing it to the buffer
	err = tmpl.Execute(&buf, templateData)
	if err != nil {
		fmt.Printf("Error: Failed to generate resource %s\n%s\n", name, err)
		os.Exit(1)
	}

	return buf.String()

}

// Required returns a comma separated list of the required properties for this resource
func (r Resource) Required() string {
	required := []string{}

	for name, property := range r.Properties {
		if property.Required {
			required = append(required, `"`+name+`"`)
		}
	}

	// As Go doesn't provide ordering guarentees for maps, we should
	// sort the required property names by alphabetical order so that
	// they don't shuffle on every generation, and cause annoying commit diffs
	sort.Strings(required)

	return strings.Join(required, ", ")
}
