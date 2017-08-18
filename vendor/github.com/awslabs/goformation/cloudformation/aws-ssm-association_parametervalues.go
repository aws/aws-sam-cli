package cloudformation

// AWSSSMAssociation_ParameterValues AWS CloudFormation Resource (AWS::SSM::Association.ParameterValues)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ssm-association-parametervalues.html
type AWSSSMAssociation_ParameterValues struct {

	// ParameterValues AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ssm-association-parametervalues.html#cfn-ssm-association-parametervalues-parametervalues
	ParameterValues []string `json:"ParameterValues,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSSSMAssociation_ParameterValues) AWSCloudFormationType() string {
	return "AWS::SSM::Association.ParameterValues"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSSSMAssociation_ParameterValues) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
