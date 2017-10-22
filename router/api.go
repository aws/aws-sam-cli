package router

import (
	"fmt"
	"log"
	"io/ioutil"
	"encoding/json"

	"github.com/awslabs/goformation/cloudformation"
	"github.com/go-openapi/spec"
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
	jsonDefinition, err := api.Swagger();

	if err != nil {
		// this is our own error so we return it directly
		return nil, err
	}
	swagger := spec.Swagger{}
	err = swagger.UnmarshalJSON(jsonDefinition)

	if err != nil {
		return nil, fmt.Errorf("Cannot parse Swagger definition: %s", err.Error())
	}

	mounts := []*ServerlessRouterMount{}
	log.Printf("Reading paths from Swagger")

	for path, pathItem := range swagger.Paths.Paths {

		if pathItem.Get != nil {
			mounts = append(mounts, api.createMount(path, "get", pathItem.Get))
		}
		if pathItem.Post != nil {
			mounts = append(mounts, api.createMount(path, "post", pathItem.Post))
		}
		if pathItem.Put != nil {
			mounts = append(mounts, api.createMount(path, "put", pathItem.Put))
		}
		if pathItem.Patch != nil {
			mounts = append(mounts, api.createMount(path, "patch", pathItem.Patch))
		}
		if pathItem.Delete != nil {
			mounts = append(mounts, api.createMount(path, "delete", pathItem.Delete))
		}
		if pathItem.Options != nil {
			mounts = append(mounts, api.createMount(path, "options", pathItem.Options))
		}
	}

	return mounts, nil
}

func (api *AWSServerlessApi) createMount(path string, verb string, method *spec.Operation) *(ServerlessRouterMount) {
	newMount := &ServerlessRouterMount{
		Name: path,
		Path: path,
		Method: verb,
	}

	integrationData, available := method.Extensions["x-amazon-apigateway-integration"]
	if !available {
		log.Printf("No integration defined")
		return newMount
	}
	integrationJson, err := json.Marshal(integrationData);
	if err != nil {
		log.Printf("Could not parse integration data to json")
		return newMount
	}

	integration := ApiGatewayIntegration{}
	err = json.Unmarshal(integrationJson, &integration)

	// I'm not going to treat this as a fatal error. We can still pick up from the list of functions
	// integration data may not be defined up at all.
	if err != nil {
		log.Printf("Could not Unmarshal integration: %s", err.Error())
		return newMount
	}

	functionName, err := integration.GetFunctionArn()

	if err != nil {
		log.Printf("Could not extract Lambda function ARN: %s", err.Error())
	}
	newMount.IntegrationArn = functionName

	return newMount;
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
	data, err := ioutil.ReadFile(uri)
	if err != nil {
		return nil, fmt.Errorf("Cannot read local Swagger definition (%s): %s", uri, err.Error())
	}
	return data, nil
}

func (api *AWSServerlessApi) getSwaggerFromS3Location(cloudformation.AWSServerlessApi_S3Location) ([]byte, error) {
	return nil, nil
}

func (api *AWSServerlessApi) getSwaggerFromString(input string) ([]byte, error) {
	return []byte(input), nil
}

func (api *AWSServerlessApi) getSwaggerFromMap(input map[string]interface{}) ([]byte, error) {
	return json.Marshal(input)
}
