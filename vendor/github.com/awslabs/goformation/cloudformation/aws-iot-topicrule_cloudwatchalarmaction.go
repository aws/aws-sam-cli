package cloudformation

// AWSIoTTopicRule_CloudwatchAlarmAction AWS CloudFormation Resource (AWS::IoT::TopicRule.CloudwatchAlarmAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchalarm.html
type AWSIoTTopicRule_CloudwatchAlarmAction struct {

	// AlarmName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchalarm.html#cfn-iot-cloudwatchalarm-alarmname
	AlarmName string `json:"AlarmName,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchalarm.html#cfn-iot-cloudwatchalarm-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// StateReason AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchalarm.html#cfn-iot-cloudwatchalarm-statereason
	StateReason string `json:"StateReason,omitempty"`

	// StateValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchalarm.html#cfn-iot-cloudwatchalarm-statevalue
	StateValue string `json:"StateValue,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_CloudwatchAlarmAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.CloudwatchAlarmAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_CloudwatchAlarmAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
