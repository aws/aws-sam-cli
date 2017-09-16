package cloudformation

// AWSIoTTopicRule_PutItemInput AWS CloudFormation Resource (AWS::IoT::TopicRule.PutItemInput)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrule-putiteminput.html
type AWSIoTTopicRule_PutItemInput struct {

	// TableName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrule-putiteminput.html#cfn-iot-topicrule-putiteminput-tablename
	TableName string `json:"TableName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_PutItemInput) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.PutItemInput"
}
