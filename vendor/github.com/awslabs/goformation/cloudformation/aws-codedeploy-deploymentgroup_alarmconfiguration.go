package cloudformation

// AWSCodeDeployDeploymentGroup_AlarmConfiguration AWS CloudFormation Resource (AWS::CodeDeploy::DeploymentGroup.AlarmConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-alarmconfiguration.html
type AWSCodeDeployDeploymentGroup_AlarmConfiguration struct {

	// Alarms AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-alarmconfiguration.html#cfn-codedeploy-deploymentgroup-alarmconfiguration-alarms
	Alarms []AWSCodeDeployDeploymentGroup_Alarm `json:"Alarms,omitempty"`

	// Enabled AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-alarmconfiguration.html#cfn-codedeploy-deploymentgroup-alarmconfiguration-enabled
	Enabled bool `json:"Enabled,omitempty"`

	// IgnorePollAlarmFailure AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-alarmconfiguration.html#cfn-codedeploy-deploymentgroup-alarmconfiguration-ignorepollalarmfailure
	IgnorePollAlarmFailure bool `json:"IgnorePollAlarmFailure,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodeDeployDeploymentGroup_AlarmConfiguration) AWSCloudFormationType() string {
	return "AWS::CodeDeploy::DeploymentGroup.AlarmConfiguration"
}
