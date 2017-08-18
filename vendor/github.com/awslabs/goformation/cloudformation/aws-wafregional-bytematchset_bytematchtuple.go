package cloudformation

// AWSWAFRegionalByteMatchSet_ByteMatchTuple AWS CloudFormation Resource (AWS::WAFRegional::ByteMatchSet.ByteMatchTuple)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html
type AWSWAFRegionalByteMatchSet_ByteMatchTuple struct {

	// FieldToMatch AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html#cfn-wafregional-bytematchset-bytematchtuple-fieldtomatch
	FieldToMatch *AWSWAFRegionalByteMatchSet_FieldToMatch `json:"FieldToMatch,omitempty"`

	// PositionalConstraint AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html#cfn-wafregional-bytematchset-bytematchtuple-positionalconstraint
	PositionalConstraint string `json:"PositionalConstraint,omitempty"`

	// TargetString AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html#cfn-wafregional-bytematchset-bytematchtuple-targetstring
	TargetString string `json:"TargetString,omitempty"`

	// TargetStringBase64 AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html#cfn-wafregional-bytematchset-bytematchtuple-targetstringbase64
	TargetStringBase64 string `json:"TargetStringBase64,omitempty"`

	// TextTransformation AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-bytematchset-bytematchtuple.html#cfn-wafregional-bytematchset-bytematchtuple-texttransformation
	TextTransformation string `json:"TextTransformation,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSWAFRegionalByteMatchSet_ByteMatchTuple) AWSCloudFormationType() string {
	return "AWS::WAFRegional::ByteMatchSet.ByteMatchTuple"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSWAFRegionalByteMatchSet_ByteMatchTuple) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
