package cloudformation

// AWSWAFRegionalSizeConstraintSet_SizeConstraint AWS CloudFormation Resource (AWS::WAFRegional::SizeConstraintSet.SizeConstraint)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-sizeconstraintset-sizeconstraint.html
type AWSWAFRegionalSizeConstraintSet_SizeConstraint struct {

	// ComparisonOperator AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-sizeconstraintset-sizeconstraint.html#cfn-wafregional-sizeconstraintset-sizeconstraint-comparisonoperator
	ComparisonOperator string `json:"ComparisonOperator,omitempty"`

	// FieldToMatch AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-sizeconstraintset-sizeconstraint.html#cfn-wafregional-sizeconstraintset-sizeconstraint-fieldtomatch
	FieldToMatch *AWSWAFRegionalSizeConstraintSet_FieldToMatch `json:"FieldToMatch,omitempty"`

	// Size AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-sizeconstraintset-sizeconstraint.html#cfn-wafregional-sizeconstraintset-sizeconstraint-size
	Size int `json:"Size,omitempty"`

	// TextTransformation AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafregional-sizeconstraintset-sizeconstraint.html#cfn-wafregional-sizeconstraintset-sizeconstraint-texttransformation
	TextTransformation string `json:"TextTransformation,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSWAFRegionalSizeConstraintSet_SizeConstraint) AWSCloudFormationType() string {
	return "AWS::WAFRegional::SizeConstraintSet.SizeConstraint"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSWAFRegionalSizeConstraintSet_SizeConstraint) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
