package cloudformation

// AWSIoTTopicRule_TopicRulePayload AWS CloudFormation Resource (AWS::IoT::TopicRule.TopicRulePayload)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html
type AWSIoTTopicRule_TopicRulePayload struct {

	// Actions AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html#cfn-iot-topicrulepayload-actions
	Actions []AWSIoTTopicRule_Action `json:"Actions,omitempty"`

	// AwsIotSqlVersion AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html#cfn-iot-topicrulepayload-awsiotsqlversion
	AwsIotSqlVersion string `json:"AwsIotSqlVersion,omitempty"`

	// Description AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html#cfn-iot-topicrulepayload-description
	Description string `json:"Description,omitempty"`

	// RuleDisabled AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html#cfn-iot-topicrulepayload-ruledisabled
	RuleDisabled bool `json:"RuleDisabled,omitempty"`

	// Sql AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-topicrulepayload.html#cfn-iot-topicrulepayload-sql
	Sql string `json:"Sql,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_TopicRulePayload) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.TopicRulePayload"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_TopicRulePayload) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
