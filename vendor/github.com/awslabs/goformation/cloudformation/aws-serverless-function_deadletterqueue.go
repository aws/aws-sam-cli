package cloudformation

// AWSServerlessFunction_DeadLetterQueue AWS CloudFormation Resource (AWS::Serverless::Function.DeadLetterQueue)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#deadletterqueue-object
type AWSServerlessFunction_DeadLetterQueue struct {

	// TargetArn AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
	TargetArn string `json:"TargetArn,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_DeadLetterQueue) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.DeadLetterQueue"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSServerlessFunction_DeadLetterQueue) AWSCloudFormationSpecificationVersion() string {
	return "2016-10-31"
}
