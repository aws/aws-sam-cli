package router

import (
	"fmt"

	"github.com/awslabs/goformation/cloudformation"
)

// AWSServerlessApi wraps GoFormation's AWS::Serverless::Api definition
// and adds some convenience methods for extracting the ServerlessRouterMount's
// from the swagger defintion etc.
type AWSServerlessApi struct {
	*cloudformation.AWSServerlessApi
}

// Mounts fetches an array of the ServerlessRouterMount's for this API.
// These contain the path, method and handler function for each mount point.
func (api *AWSServerlessApi) Mounts() ([]*ServerlessRouterMount, error) {
	return nil, nil
}

// Swagger gets the swagger definition for the API.
// Returns the swagger definition as a []byte of JSON.
func (api *AWSServerlessApi) Swagger() ([]byte, error) {

	// The swagger definition can be passed in 1 of 4 ways:

	// 1. A definition URI defined as a string
	if api.DefinitionUri != nil {
		if api.DefinitionUri.String != nil {
			return api.getSwaggerFromURI(*api.DefinitionUri.String)
		}
	}

	// 2. A definition URI defined as an S3 Location
	if api.DefinitionUri != nil {
		if api.DefinitionUri.S3Location != nil {
			return api.getSwaggerFromS3Location(*api.DefinitionUri.S3Location)
		}
	}

	if api.DefinitionBody != nil {

		switch val := api.DefinitionBody.(type) {

		case string:
			// 3. A definition body defined as JSON (which will unmarshal to a string)
			return api.getSwaggerFromString(val)

		case map[string]interface{}:
			// 4. A definition body defined as YAML (which will unmarshal to map[string]interface{})
			return api.getSwaggerFromMap(val)
		}

	}

	return nil, fmt.Errorf("no swagger definition found")

}

func (api *AWSServerlessApi) getSwaggerFromURI(uri string) ([]byte, error) {
	return nil, nil
}

func (api *AWSServerlessApi) getSwaggerFromS3Location(cloudformation.AWSServerlessApi_S3Location) ([]byte, error) {
	return nil, nil
}

func (api *AWSServerlessApi) getSwaggerFromString(input string) ([]byte, error) {
	return nil, nil
}

func (api *AWSServerlessApi) getSwaggerFromMap(input map[string]interface{}) ([]byte, error) {
	return nil, nil
}
