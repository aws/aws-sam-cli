package cloudformation

// AWSLambdaFunction_TracingConfig AWS CloudFormation Resource (AWS::Lambda::Function.TracingConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-function-tracingconfig.html
type AWSLambdaFunction_TracingConfig struct {

	// Mode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-function-tracingconfig.html#cfn-lambda-function-tracingconfig-mode
	Mode string `json:"Mode,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSLambdaFunction_TracingConfig) AWSCloudFormationType() string {
	return "AWS::Lambda::Function.TracingConfig"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSLambdaFunction_TracingConfig) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
