package cloudformation

// AWSSSMPatchBaseline_RuleGroup AWS CloudFormation Resource (AWS::SSM::PatchBaseline.RuleGroup)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ssm-patchbaseline-rulegroup.html
type AWSSSMPatchBaseline_RuleGroup struct {

	// PatchRules AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ssm-patchbaseline-rulegroup.html#cfn-ssm-patchbaseline-rulegroup-patchrules
	PatchRules []AWSSSMPatchBaseline_Rule `json:"PatchRules,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSSSMPatchBaseline_RuleGroup) AWSCloudFormationType() string {
	return "AWS::SSM::PatchBaseline.RuleGroup"
}
