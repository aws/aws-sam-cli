package main

import (
	"encoding/json"
	"io/ioutil"
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/awslabs/goformation/cloudformation"
)

/**
 The Environment Variable Saga..

 There are two types of environment variables
 	- Lambda runtime variables starting with "AWS_" and passed to every function
 	- Custom environment variables defined in SAM template for each function

 Custom environment variables defined in the SAM template can contain hard-coded
 values or fetch from a stack parameter or use Intrinsics to generate a value at
 at stack creation time like ARNs. It can get complicated to support all cases

 Instead we will parse only hard-coded values from the template. For the rest,
 users can supply values through the Shell's environment or the env-var override
 CLI argument. If a value is provided through more than one method, the method
 with higher priority will win.

 Priority (Highest to lowest)
	Env-Var CLI argument
	Shell's Environment
	Hard-coded values from template

 This priority also applies to AWS_* system variables
*/

func getEnvironmentVariables(logicalID string, function *cloudformation.AWSServerlessFunction, overrideFile string) map[string]string {

	env := getEnvDefaults(function)
	osenv := getEnvFromOS()
	overrides := getEnvOverrides(logicalID, overrideFile)

	if function.Environment != nil {
		for name, value := range function.Environment.Variables {

			// hard-coded values, lowest priority
			if stringedValue, ok := toStringMaybe(value); ok {
				// Get only hard-coded values from the template
				env[name] = stringedValue
			}

			// Shell's environment, second priority
			if value, ok := osenv[name]; ok {
				env[name] = value
			}

			// EnvVars overrides provided by customer, highest priority
			if len(overrides) > 0 {
				if value, ok := overrides[name]; ok {
					env[name] = value
				}
			}
		}
	}

	return env

}

func getEnvDefaults(function *cloudformation.AWSServerlessFunction) map[string]string {

	creds := getSessionOrDefaultCreds()

	// Variables available in Lambda execution environment for all functions (AWS_* variables)
	env := map[string]string{
		"AWS_SAM_LOCAL":                   "true",
		"AWS_REGION":                      creds["region"],
		"AWS_DEFAULT_REGION":              creds["region"],
		"AWS_ACCESS_KEY_ID":               creds["key"],
		"AWS_SECRET_ACCESS_KEY":           creds["secret"],
		"AWS_LAMBDA_FUNCTION_MEMORY_SIZE": strconv.Itoa(int(function.MemorySize)),
		"AWS_LAMBDA_FUNCTION_TIMEOUT":     strconv.Itoa(int(function.Timeout)),
		"AWS_LAMBDA_FUNCTION_HANDLER":     function.Handler,
		// "AWS_ACCOUNT_ID=",
		// "AWS_LAMBDA_EVENT_BODY=",
		// "AWS_REGION=",
		// "AWS_LAMBDA_FUNCTION_NAME=",
		// "AWS_LAMBDA_FUNCTION_VERSION=",
	}

	if token, ok := creds["sessiontoken"]; ok && token != "" {
		env["AWS_SESSION_TOKEN"] = token
	}

	return env

}

func getEnvOverrides(logicalID string, filename string) map[string]string {

	if len(filename) > 0 {

		data, err := ioutil.ReadFile(filename)
		if err != nil {
			log.Printf("Could not read environment overrides from %s: %s\n", filename, err)
			return map[string]string{}
		}

		// This is a JSON of structure {FunctionName: {key:value}, FunctionName: {key:value}}
		overrides := map[string]map[string]string{}
		if err = json.Unmarshal(data, &overrides); err != nil {
			log.Printf("Invalid environment override file %s: %s\n", filename, err)
			return map[string]string{}
		}

		return overrides[logicalID]

	}

	return map[string]string{}

}

func getSessionOrDefaultCreds() map[string]string {

	region := "us-east-1"
	key := "defaultkey"
	secret := "defaultsecret"

	result := map[string]string{
		"region": region,
		"key":    key,
		"secret": secret,
	}

	// Obtain AWS credentials and pass them through to the container runtime via env variables
	if sess, err := session.NewSession(); err == nil {
		if creds, err := sess.Config.Credentials.Get(); err == nil {
			if *sess.Config.Region != "" {
				result["region"] = *sess.Config.Region
			}

			result["key"] = creds.AccessKeyID
			result["secret"] = creds.SecretAccessKey
			if creds.SessionToken != "" {
				result["sessiontoken"] = creds.SessionToken
			}
		}
	}

	return result
}

func getEnvFromOS() map[string]string {

	result := map[string]string{}
	for _, value := range os.Environ() {
		keyVal := strings.Split(value, "=")
		result[keyVal[0]] = keyVal[1]
	}

	return result
}

// Converts the input to string if it is a primitive type, Otherwise returns nil
func toStringMaybe(value interface{}) (string, bool) {

	switch value.(type) {
	case string:
		return value.(string), true
	case int:
		return strconv.Itoa(value.(int)), true
	case float32, float64:
		return strconv.FormatFloat(value.(float64), 'f', -1, 64), true
	case bool:
		return strconv.FormatBool(value.(bool)), true
	default:
		return "", false
	}

}
