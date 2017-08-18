package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/format"
	"io/ioutil"
	"net/http"
	"os"
	"strings"
	"text/template"
)

// SpecURL is the HTTP URL of the latest AWS CloudFormation Resource Specification
const SpecURL = "https://d1uauaxba7bl26.cloudfront.net/latest/gzip/CloudFormationResourceSpecification.json"

func main() {

	// Fetch the latest CloudFormation Resource Specification
	fmt.Printf("Download the latest AWS CloudFormation Resource Specification...\n")
	response, err := http.Get(SpecURL)
	if err != nil {
		fmt.Printf("Error: Failed to fetch AWS CloudFormation Resource Specification\n%s\n", err)
		os.Exit(1)
	}

	// Read all of the retrieved data at once (~70KB)
	cfData, err := ioutil.ReadAll(response.Body)
	if err != nil {
		fmt.Printf("Error: Failed to read AWS CloudFormation Resource Specification\n%s\n", err)
		os.Exit(1)
	}

	// Unmarshall the JSON specification data to objects
	cfSpec := &CloudFormationResourceSpecification{}
	if err := json.Unmarshal(cfData, cfSpec); err != nil {
		fmt.Printf("Error: Failed to parse AWS CloudFormation Resource Specification\n%s\n", err)
		os.Exit(1)
	}

	// Generate all of the AWS Cloudformation resources
	cfCount := generateFromSpec(cfSpec)

	// Fetch the latest AWS SAM specification
	samData, err := ioutil.ReadFile("generate/sam-2016-10-31.json")
	if err != nil {
		fmt.Printf("Error: Failed to read AWS SAM Resource Specification\n%s\n", err)
		os.Exit(1)
	}

	// Unmarshall the JSON specification data to objects
	samSpec := &CloudFormationResourceSpecification{}
	if err := json.Unmarshal(samData, samSpec); err != nil {
		fmt.Printf("Error: Failed to parse AWS SAM Resource Specification\n%s\n", err)
		os.Exit(1)
	}

	// Generate all of the AWS Cloudformation resources
	samCount := generateFromSpec(samSpec)

	// Generate the JSON-Schema
	schemaFilename := "schema/cloudformation.schema.json"
	generateSchema(schemaFilename, cfSpec)

	fmt.Printf("\n")
	fmt.Printf("Generated %d AWS CloudFormation resources from specification v%s\n", cfCount, cfSpec.ResourceSpecificationVersion)
	fmt.Printf("Generated %d AWS SAM resources from specification v%s\n", samCount, samSpec.ResourceSpecificationVersion)
	fmt.Printf("Generated JSON Schema: %s\n", schemaFilename)

}

func generateFromSpec(spec *CloudFormationResourceSpecification) int {

	count := 0

	// Write all of the resources, using a template
	for name, resource := range spec.Resources {
		generateResources(name, resource, false, spec)
		fmt.Printf("Generated resource: %s\n", name)
		count++
	}

	// Write all of the custom properties, using a template
	for name, property := range spec.Properties {
		generateResources(name, property, true, spec)
		fmt.Printf("Generated custom property type: %s\n", name)
		count++
	}

	return count

}

// generateResources generates Go structs for all of the resources and custom property types
// found in a CloudformationResourceSpecification
func generateResources(name string, resource Resource, isCustomProperty bool, spec *CloudFormationResourceSpecification) {

	// Open the resource template
	tmpl, err := template.ParseFiles("generate/templates/resource.template")
	if err != nil {
		fmt.Printf("Error: Failed to load resource template\n%s\n", err)
		os.Exit(1)
	}

	// Pass in the following information into the template
	sname := structName(name)
	structNameParts := strings.Split(name, ".")
	basename := structName(structNameParts[0])

	templateData := struct {
		Name             string
		StructName       string
		Basename         string
		Resource         Resource
		IsCustomProperty bool
		Version          string
	}{
		Name:             name,
		StructName:       sname,
		Basename:         basename,
		Resource:         resource,
		IsCustomProperty: isCustomProperty,
		Version:          spec.ResourceSpecificationVersion,
	}

	// Execute the template, writing it to file
	var buf bytes.Buffer
	err = tmpl.Execute(&buf, templateData)
	if err != nil {
		fmt.Printf("Error: Failed to generate resource %s\n%s\n", name, err)
		os.Exit(1)
	}

	// Format the generated Go file with gofmt
	formatted, err := format.Source(buf.Bytes())
	if err != nil {
		fmt.Printf("Error: Failed to format Go file for resource %s\n%s\n", name, err)
		os.Exit(1)
	}

	// Write the file out
	if err := ioutil.WriteFile("cloudformation/"+filename(name), formatted, 0644); err != nil {
		fmt.Printf("Error: Failed to write JSON Schema\n%s\n", err)
		os.Exit(1)
	}

}

// generateResources generates a JSON Schema for all of the resources and custom property types
// found in a CloudformationResourceSpecification
func generateSchema(filename string, spec *CloudFormationResourceSpecification) {

	// Open the schema template and setup a counter function that will
	// available in the template to be used to detect when trailing commas
	// are required in the JSON when looping through maps
	tmpl, err := template.New("schema.template").Funcs(template.FuncMap{
		"counter": counter,
	}).ParseFiles("generate/templates/schema.template")

	var buf bytes.Buffer

	// Execute the template, writing it to file
	err = tmpl.Execute(&buf, spec)
	if err != nil {
		fmt.Printf("Error: Failed to generate JSON Schema\n%s\n", err)
		os.Exit(1)
	}

	// Parse it to JSON objects and back again to format it
	var j interface{}
	if err := json.Unmarshal(buf.Bytes(), &j); err != nil {
		fmt.Printf("Error: Failed to unmarhal JSON Schema\n%s\n", err)
		os.Exit(1)
	}

	formatted, err := json.MarshalIndent(j, "", "    ")
	if err != nil {
		fmt.Printf("Error: Failed to marshal JSON Schema\n%s\n", err)
		os.Exit(1)
	}

	if err := ioutil.WriteFile(filename, formatted, 0644); err != nil {
		fmt.Printf("Error: Failed to write JSON Schema\n%s\n", err)
		os.Exit(1)
	}

}

func generatePolymorphicProperty(name string, property Property) {

	// Open the polymorphic property template
	tmpl, err := template.New("polymorphic-property.template").Funcs(template.FuncMap{
		"convertToGoType": convertTypeToGo,
	}).ParseFiles("generate/templates/polymorphic-property.template")

	nameParts := strings.Split(name, "_")

	types := append([]string{}, property.PrimitiveTypes...)
	types = append(types, property.PrimitiveItemTypes...)
	types = append(types, property.ItemTypes...)
	types = append(types, property.Types...)

	templateData := struct {
		Name        string
		Basename    string
		Property    Property
		Types       []string
		TypesJoined string
	}{
		Name:        name,
		Basename:    nameParts[0],
		Property:    property,
		Types:       types,
		TypesJoined: conjoin("or", types),
	}

	// Execute the template, writing it to file
	var buf bytes.Buffer
	err = tmpl.Execute(&buf, templateData)
	if err != nil {
		fmt.Printf("Error: Failed to generate polymorphic property %s\n%s\n", name, err)
		os.Exit(1)
	}

	// Format the generated Go file with gofmt
	formatted, err := format.Source(buf.Bytes())
	if err != nil {
		fmt.Printf("Error: Failed to format Go file for resource %s\n%s\n", name, err)
		os.Exit(1)
	}

	// Write the file out
	if err := ioutil.WriteFile("cloudformation/"+filename(name), formatted, 0644); err != nil {
		fmt.Printf("Error: Failed to write JSON Schema\n%s\n", err)
		os.Exit(1)
	}

	fmt.Printf("Generated polymorphic property: %s\n", name)

}

// counter is used within the JSON Schema template to determin whether or not
// to put a comma after a JSON resource (i.e. if it's the last element, then no comma)
// see: http://android.wekeepcoding.com/article/10126058/Go+template+remove+the+last+comma+in+range+loop
func counter(length int) func() int {
	i := length
	return func() int {
		i--
		return i
	}
}

func conjoin(conj string, items []string) string {
	if len(items) == 0 {
		return ""
	}
	if len(items) == 1 {
		return items[0]
	}
	if len(items) == 2 { // "a and b" not "a, and b"
		return items[0] + " " + conj + " " + items[1]
	}

	sep := ", "
	pieces := []string{items[0]}
	for _, item := range items[1 : len(items)-1] {
		pieces = append(pieces, sep, item)
	}
	pieces = append(pieces, sep, conj, " ", items[len(items)-1])

	return strings.Join(pieces, "")
}
