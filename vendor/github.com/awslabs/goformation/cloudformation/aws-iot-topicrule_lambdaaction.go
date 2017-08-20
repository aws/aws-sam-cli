package cloudformation

// AWSIoTTopicRule_LambdaAction AWS CloudFormation Resource (AWS::IoT::TopicRule.LambdaAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-lambda.html
type AWSIoTTopicRule_LambdaAction struct {

	// FunctionArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-lambda.html#cfn-iot-lambda-functionarn
	FunctionArn string `json:"FunctionArn,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_LambdaAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.LambdaAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_LambdaAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
