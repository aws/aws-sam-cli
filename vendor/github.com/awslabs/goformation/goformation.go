package goformation

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"strings"

	"github.com/awslabs/goformation/cloudformation"
	"github.com/awslabs/goformation/intrinsics"
	"github.com/ghodss/yaml"
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
		data, err = yaml.YAMLToJSON(data)
		if err != nil {
			return nil, fmt.Errorf("invalid YAML template: %s", err)
		}

	}

	return Parse(data)

}

// Parse an AWS CloudFormation template (expects a []byte of valid JSON)
func Parse(data []byte) (*cloudformation.Template, error) {

	// Process all AWS CloudFormation intrinsic functions (e.g. Fn::Join)
	intrinsified, err := intrinsics.Process(data, nil)
	if err != nil {
		return nil, err
	}

	template := &cloudformation.Template{}
	if err := json.Unmarshal(intrinsified, template); err != nil {
		return nil, err
	}

	return template, nil

}
