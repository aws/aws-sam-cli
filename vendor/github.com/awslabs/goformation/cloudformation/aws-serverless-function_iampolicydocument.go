package cloudformation

// AWSServerlessFunction_IAMPolicyDocument AWS CloudFormation Resource (AWS::Serverless::Function.IAMPolicyDocument)
// See: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies.html
type AWSServerlessFunction_IAMPolicyDocument struct {

	// Statement AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies.html
	Statement interface{} `json:"Statement,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_IAMPolicyDocument) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.IAMPolicyDocument"
}
