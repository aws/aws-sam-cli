package cloudformation

// AWSIoTTopicRule_RepublishAction AWS CloudFormation Resource (AWS::IoT::TopicRule.RepublishAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-republish.html
type AWSIoTTopicRule_RepublishAction struct {

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-republish.html#cfn-iot-republish-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// Topic AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-republish.html#cfn-iot-republish-topic
	Topic string `json:"Topic,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_RepublishAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.RepublishAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_RepublishAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
