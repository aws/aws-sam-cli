package cloudformation

// AWSGlueTrigger_Predicate AWS CloudFormation Resource (AWS::Glue::Trigger.Predicate)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-predicate.html
type AWSGlueTrigger_Predicate struct {

	// Conditions AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-predicate.html#cfn-glue-trigger-predicate-conditions
	Conditions []AWSGlueTrigger_Condition `json:"Conditions,omitempty"`

	// Logical AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-trigger-predicate.html#cfn-glue-trigger-predicate-logical
	Logical string `json:"Logical,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueTrigger_Predicate) AWSCloudFormationType() string {
	return "AWS::Glue::Trigger.Predicate"
}
