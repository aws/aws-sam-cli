package cloudformation

// AWSIoTTopicRule_FirehoseAction AWS CloudFormation Resource (AWS::IoT::TopicRule.FirehoseAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-firehose.html
type AWSIoTTopicRule_FirehoseAction struct {

	// DeliveryStreamName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-firehose.html#cfn-iot-firehose-deliverystreamname
	DeliveryStreamName string `json:"DeliveryStreamName,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-firehose.html#cfn-iot-firehose-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// Separator AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-firehose.html#cfn-iot-firehose-separator
	Separator string `json:"Separator,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_FirehoseAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.FirehoseAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_FirehoseAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
