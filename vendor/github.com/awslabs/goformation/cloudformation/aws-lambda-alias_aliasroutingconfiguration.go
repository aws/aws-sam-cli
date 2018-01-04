package cloudformation

// AWSLambdaAlias_AliasRoutingConfiguration AWS CloudFormation Resource (AWS::Lambda::Alias.AliasRoutingConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-alias-aliasroutingconfiguration.html
type AWSLambdaAlias_AliasRoutingConfiguration struct {

	// AdditionalVersionWeights AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-alias-aliasroutingconfiguration.html#cfn-lambda-alias-aliasroutingconfiguration-additionalversionweights
	AdditionalVersionWeights []AWSLambdaAlias_VersionWeight `json:"AdditionalVersionWeights,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSLambdaAlias_AliasRoutingConfiguration) AWSCloudFormationType() string {
	return "AWS::Lambda::Alias.AliasRoutingConfiguration"
}
