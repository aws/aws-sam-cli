package cloudformation

// AWSEventsRule_RunCommandParameters AWS CloudFormation Resource (AWS::Events::Rule.RunCommandParameters)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-events-rule-runcommandparameters.html
type AWSEventsRule_RunCommandParameters struct {

	// RunCommandTargets AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-events-rule-runcommandparameters.html#cfn-events-rule-runcommandparameters-runcommandtargets
	RunCommandTargets []AWSEventsRule_RunCommandTarget `json:"RunCommandTargets,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEventsRule_RunCommandParameters) AWSCloudFormationType() string {
	return "AWS::Events::Rule.RunCommandParameters"
}
