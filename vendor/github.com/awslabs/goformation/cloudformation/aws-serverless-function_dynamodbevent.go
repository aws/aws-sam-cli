package cloudformation

// AWSServerlessFunction_DynamoDBEvent AWS CloudFormation Resource (AWS::Serverless::Function.DynamoDBEvent)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#dynamodb
type AWSServerlessFunction_DynamoDBEvent struct {

	// BatchSize AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#dynamodb
	BatchSize int `json:"BatchSize,omitempty"`

	// StartingPosition AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#dynamodb
	StartingPosition string `json:"StartingPosition,omitempty"`

	// Stream AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#dynamodb
	Stream string `json:"Stream,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_DynamoDBEvent) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.DynamoDBEvent"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSServerlessFunction_DynamoDBEvent) AWSCloudFormationSpecificationVersion() string {
	return "2016-10-31"
}
