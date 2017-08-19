package goformation

import (
	"encoding/json"
	"io/ioutil"
	"strings"

	"github.com/awslabs/goformation/cloudformation"
	"github.com/awslabs/goformation/intrinsics"
)

//go:generate generate/generate.sh

// Open and parse a AWS CloudFormation template from file.
// Works with either JSON or YAML formatted templates.
func Open(filename string) (*cloudformation.Template, error) {

	data, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, err
	}

	if strings.HasSuffix(filename, ".yaml") || strings.HasSuffix(filename, ".yml") {
		return ParseYAML(data)
	}

	return ParseJSON(data)

}

// ParseYAML an AWS CloudFormation template (expects a []byte of valid YAML)
func ParseYAML(data []byte) (*cloudformation.Template, error) {
	// Process all AWS CloudFormation intrinsic functions (e.g. Fn::Join)
	intrinsified, err := intrinsics.ProcessYAML(data, nil)
	if err != nil {
		return nil, err
	}

	return unmarshal(intrinsified)

}

// ParseJSON an AWS CloudFormation template (expects a []byte of valid JSON)
func ParseJSON(data []byte) (*cloudformation.Template, error) {

	// Process all AWS CloudFormation intrinsic functions (e.g. Fn::Join)
	intrinsified, err := intrinsics.ProcessJSON(data, nil)
	if err != nil {
		return nil, err
	}

	return unmarshal(intrinsified)

}

func unmarshal(data []byte) (*cloudformation.Template, error) {

	template := &cloudformation.Template{}
	if err := json.Unmarshal(data, template); err != nil {
		return nil, err
	}

	return template, nil

}
