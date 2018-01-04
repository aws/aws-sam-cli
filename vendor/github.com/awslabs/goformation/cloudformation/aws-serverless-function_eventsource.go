package cloudformation

// AWSServerlessFunction_EventSource AWS CloudFormation Resource (AWS::Serverless::Function.EventSource)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#event-source-object
type AWSServerlessFunction_EventSource struct {

	// Properties AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#event-source-types
	Properties *AWSServerlessFunction_Properties `json:"Properties,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#event-source-object
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_EventSource) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.EventSource"
}
