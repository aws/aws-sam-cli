package cloudformation

// AWSWAFRegionalWebACL_Action AWS CloudFormation Resource (AWS::WAFRegional::WebACL.Action)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-webacl-action.html
type AWSWAFRegionalWebACL_Action struct {

	// Type AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-webacl-action.html#cfn-wafregional-webacl-action-type
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSWAFRegionalWebACL_Action) AWSCloudFormationType() string {
	return "AWS::WAFRegional::WebACL.Action"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSWAFRegionalWebACL_Action) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
