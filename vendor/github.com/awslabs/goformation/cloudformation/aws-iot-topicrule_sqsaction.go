package cloudformation

// AWSIoTTopicRule_SqsAction AWS CloudFormation Resource (AWS::IoT::TopicRule.SqsAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-sqs.html
type AWSIoTTopicRule_SqsAction struct {

	// QueueUrl AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-sqs.html#cfn-iot-sqs-queueurl
	QueueUrl string `json:"QueueUrl,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-sqs.html#cfn-iot-sqs-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// UseBase64 AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-sqs.html#cfn-iot-sqs-usebase64
	UseBase64 bool `json:"UseBase64,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_SqsAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.SqsAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_SqsAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
