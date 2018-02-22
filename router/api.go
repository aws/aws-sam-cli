package router

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"

	"strings"

	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/awslabs/goformation/cloudformation"
	"github.com/go-openapi/spec"
	"github.com/sanathkr/go-yaml"
)

const apiGatewayIntegrationExtension = "x-amazon-apigateway-integration"
const apiGatewayAnyMethodExtension = "x-amazon-apigateway-any-method"

// temporary object. This is just used to marshal and unmarshal the any method
// API Gateway swagger extension
type ApiGatewayAnyMethod struct {
	IntegrationSettings interface{} `json:"x-amazon-apigateway-integration"`
}

// AWSServerlessApi wraps GoFormation's AWS::Serverless::Api definition
// and adds some convenience methods for extracting the ServerlessRouterMount's
// from the swagger defintion etc.
type AWSServerlessApi struct {
	*cloudformation.AWSServerlessApi
}

// Mounts fetches an array of the ServerlessRouterMount's for this API.
// These contain the path, method and handler function for each mount point.
func (api *AWSServerlessApi) Mounts() ([]*ServerlessRouterMount, error) {
	jsonDefinition, err := api.Swagger()

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

	for path, pathItem := range swagger.Paths.Paths {
		// temporary tracking of mounted methods for the current path. Used to
		// mount all non-existing methods for the any extension. This is because
		// the err from JSONLookup did not work as expected
		mappedMethods := map[string]bool{}

		for _, method := range HttpMethods {

			if operationIface, err := pathItem.JSONLookup(strings.ToLower(method)); err == nil {
				operation := spec.Operation{}
				operationJSON, err := json.Marshal(operationIface)
				if err != nil {
					return nil, fmt.Errorf("Could not parse %s operation: %s", method, err.Error())
				}
				operation.UnmarshalJSON(operationJSON)

				// the JSON will always contain the method because it's a property in the Swagger model
				// If we don't have an integration defined then we skip it.
				if operation.Extensions[apiGatewayIntegrationExtension] == nil {
					continue
				}

				integration, _ := operation.Extensions[apiGatewayIntegrationExtension]
				mounts = append(mounts, api.createMount(
					path,
					strings.ToLower(method),
					api.parseIntegrationSettings(integration)))
				mappedMethods[method] = true
			}
		}

		anyMethod, available := pathItem.Extensions[apiGatewayAnyMethodExtension]
		if available {
			// any method to json then unmarshal to temporary object
			anyMethodJSON, err := json.Marshal(anyMethod)
			if err != nil {
				return nil, fmt.Errorf("Could not marshal any method object to json")
			}

			anyMethodObject := ApiGatewayAnyMethod{}
			err = json.Unmarshal(anyMethodJSON, &anyMethodObject)

			if err != nil {
				return nil, fmt.Errorf("Could not unmarshal any method josn to object model")
			}

			for _, method := range HttpMethods {
				if _, ok := mappedMethods[method]; !ok {
					mounts = append(mounts, api.createMount(
						path,
						strings.ToLower(method),
						api.parseIntegrationSettings(anyMethodObject.IntegrationSettings)))
				}
			}
		}
	}

	return mounts, nil
}

// parses a byte[] for the API Gateway inetegration extension from a method and return
// the object representation
func (api *AWSServerlessApi) parseIntegrationSettings(integrationData interface{}) *ApiGatewayIntegration {
	integrationJSON, err := json.Marshal(integrationData)
	if err != nil {
		log.Printf("Could not parse integration data to json")
		return nil
	}

	integration := ApiGatewayIntegration{}
	err = json.Unmarshal(integrationJSON, &integration)

	if err != nil {
		log.Printf("Could not unmarshal integration data to ApiGatewayIntegration model")
		return nil
	}

	return &integration
}

func (api *AWSServerlessApi) createMount(path string, verb string, integration *ApiGatewayIntegration) *(ServerlessRouterMount) {
	newMount := &ServerlessRouterMount{
		Name:   path,
		Path:   path,
		Method: verb,
	}

	if integration == nil {
		log.Printf("No integration defined for method")
		return newMount
	}

	functionName, err := integration.GetFunctionArn()

	if err != nil {
		log.Printf("Could not extract Lambda function ARN: %s", err.Error())
	}
	newMount.IntegrationArn = functionName

	return newMount
}

// Swagger gets the swagger definition for the API.
// Returns the swagger definition as a []byte of JSON.
func (api *AWSServerlessApi) Swagger() ([]byte, error) {

	// The swagger definition can be passed in 1 of 4 ways:

	// 1. A definition URI defined as a string
	if api.DefinitionUri != nil {
		if api.DefinitionUri.String != nil {
			data, err := api.getSwaggerFromURI(*api.DefinitionUri.String)
			if err != nil {
				return nil, err
			}
			return api.ensureJSON(data)
		}
	}

	// 2. A definition URI defined as an S3 Location
	if api.DefinitionUri != nil {
		if api.DefinitionUri.S3Location != nil {
			data, err := api.getSwaggerFromS3Location(*api.DefinitionUri.S3Location)
			if err != nil {
				return nil, err
			}
			return api.ensureJSON(data)
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

func (api *AWSServerlessApi) ensureJSON(data []byte) ([]byte, error) {
	var tmpDefinition interface{}
	err := json.Unmarshal(data, &tmpDefinition)

	if err != nil { // may be yaml
		err = yaml.Unmarshal(data, &tmpDefinition)

		if err != nil {
			// we can't make it work either as json or yaml. fail :(
			return nil, err
		}
		tmpDefinition = yamlToJSON(tmpDefinition)

		outputData, err := json.Marshal(tmpDefinition)
		if err != nil {
			return nil, err
		}
		return outputData, nil
	}

	return data, nil
}

func (api *AWSServerlessApi) getSwaggerFromURI(uri string) ([]byte, error) {
	data, err := ioutil.ReadFile(uri)
	if err != nil {
		return nil, fmt.Errorf("Cannot read local Swagger definition (%s): %s", uri, err.Error())
	}
	return data, nil
}

func (api *AWSServerlessApi) getSwaggerFromS3Location(loc cloudformation.AWSServerlessApi_S3Location) ([]byte, error) {
	sess := session.Must(session.NewSession())
	client := s3.New(sess)

	objectVersion := string(loc.Version)
	s3Input := s3.GetObjectInput{
		Bucket:    &loc.Bucket,
		Key:       &loc.Key,
		VersionId: &objectVersion,
	}

	object, err := client.GetObject(&s3Input)

	if err != nil {
		return nil, fmt.Errorf("Error while fetching Swagger template from S3: %s\n%s", loc.Bucket+loc.Key, err.Error())
	}

	body, err := ioutil.ReadAll(object.Body)

	if err != nil {
		return nil, fmt.Errorf("Cannot read s3 Swagger boject body: %s", err.Error())
	}
	return body, nil
}

func (api *AWSServerlessApi) getSwaggerFromString(input string) ([]byte, error) {
	return []byte(input), nil
}

func (api *AWSServerlessApi) getSwaggerFromMap(input map[string]interface{}) ([]byte, error) {
	return json.Marshal(input)
}

// Recursively convert a map[interface{}]interface{} (yaml) to map[string]interface{} (json)
// with an additional special case for the Swagger version that makes the offical Swagger
// library very upset.
func yamlToJSON(i interface{}) interface{} {
	switch x := i.(type) {
	case map[interface{}]interface{}:
		m2 := map[string]interface{}{}
		for k, v := range x {
			// we have a special case for the swagger version, we need to convert it to a string
			if strings.ToLower(k.(string)) == "swagger" {
				m2[k.(string)] = fmt.Sprintf("%v", v)
			} else {
				m2[k.(string)] = yamlToJSON(v)
			}
		}
		return m2
	case []interface{}:
		for i, v := range x {
			x[i] = yamlToJSON(v)
		}
	}
	return i
}
