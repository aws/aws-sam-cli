package main

import (
	"regexp"
	"strings"

	"github.com/awslabs/goformation/cloudformation"
)

// addCloudformationLambdaFunctions converts all Cloudformation Lambda functions to Serverless functions. On name collisions, existing
// serverless functions are preserved.
func addCloudformationLambdaFunctions(template *cloudformation.Template, functions map[string]cloudformation.AWSServerlessFunction) {
	// convert all lambda functions to serverless functions so that invoke works for them
	for n, f := range template.GetAllAWSLambdaFunctionResources() {
		if _, found := functions[n]; !found {
			functions[n] = lambdaToServerless(f)
		}
	}
}

// dlqTypeEx is used to extract the DLQ type from an ARN
var dlqTypeEx = regexp.MustCompile(`^arn:aws(?:-[\\w]+)*:(sns|sqs):([a-zA-Z_0-9+=,.@\-/:]+)$`)

// lambdaToServerless converts a Cloudformation lambda to its Serverless counterpart. The conversion makes the following assumptions:
// * codeUri is set to nil in order to use the local code and not the remote one
// * no events are associated with the serverless function
// * no policies are added because a role is already specified
func lambdaToServerless(lambda cloudformation.AWSLambdaFunction) (serverless cloudformation.AWSServerlessFunction) {
	// serverless policies are not needed because lambdas have a role
	serverless.Policies = nil

	// no events are associated with the function
	serverless.Events = nil

	// codeUri is set to nil in order to get the code locally and not from a remote source
	serverless.CodeUri = nil

	serverless.FunctionName = lambda.FunctionName
	serverless.Description = lambda.Description
	serverless.Handler = lambda.Handler
	serverless.Timeout = lambda.Timeout
	serverless.KmsKeyArn = lambda.KmsKeyArn
	serverless.Role = lambda.Role
	serverless.Runtime = lambda.Runtime
	serverless.MemorySize = lambda.MemorySize

	if lambda.DeadLetterConfig != nil {
		dlqType := "SQS"
		match := dlqTypeEx.FindAllStringSubmatch(lambda.DeadLetterConfig.TargetArn, -1)
		if len(match) > 0 {
			dlqType = match[0][1]
		}

		serverless.DeadLetterQueue = &cloudformation.AWSServerlessFunction_DeadLetterQueue{
			TargetArn: lambda.DeadLetterConfig.TargetArn,
			Type:      strings.ToUpper(dlqType),
		}
	}

	if len(lambda.Tags) > 0 {
		tags := make(map[string]string)
		for _, t := range lambda.Tags {
			tags[t.Key] = t.Value
		}
		serverless.Tags = tags
	}

	if lambda.TracingConfig != nil {
		serverless.Tracing = lambda.TracingConfig.Mode
	}

	if lambda.Environment != nil {
		serverless.Environment = &cloudformation.AWSServerlessFunction_FunctionEnvironment{
			Variables: lambda.Environment.Variables,
		}
	}

	if lambda.VpcConfig != nil {
		serverless.VpcConfig = &cloudformation.AWSServerlessFunction_VpcConfig{
			SecurityGroupIds: lambda.VpcConfig.SecurityGroupIds,
			SubnetIds:        lambda.VpcConfig.SubnetIds,
		}
	}

	return
}
