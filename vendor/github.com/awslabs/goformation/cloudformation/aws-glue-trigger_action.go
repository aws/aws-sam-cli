package cloudformation

// AWSGlueTrigger_Action AWS CloudFormation Resource (AWS::Glue::Trigger.Action)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-action.html
type AWSGlueTrigger_Action struct {

	// Arguments AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-action.html#cfn-glue-trigger-action-arguments
	Arguments interface{} `json:"Arguments,omitempty"`

	// JobName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-action.html#cfn-glue-trigger-action-jobname
	JobName string `json:"JobName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueTrigger_Action) AWSCloudFormationType() string {
	return "AWS::Glue::Trigger.Action"
}
