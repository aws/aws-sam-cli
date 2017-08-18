package cloudformation

// AWSAutoScalingAutoScalingGroup_NotificationConfiguration AWS CloudFormation Resource (AWS::AutoScaling::AutoScalingGroup.NotificationConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-notificationconfigurations.html
type AWSAutoScalingAutoScalingGroup_NotificationConfiguration struct {

	// NotificationTypes AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-notificationconfigurations.html#cfn-as-group-notificationconfigurations-notificationtypes
	NotificationTypes []string `json:"NotificationTypes,omitempty"`

	// TopicARN AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-notificationconfigurations.html#cfn-autoscaling-autoscalinggroup-notificationconfigurations-topicarn
	TopicARN string `json:"TopicARN,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSAutoScalingAutoScalingGroup_NotificationConfiguration) AWSCloudFormationType() string {
	return "AWS::AutoScaling::AutoScalingGroup.NotificationConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSAutoScalingAutoScalingGroup_NotificationConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
