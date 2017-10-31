package cloudformation

// AWSLambdaAlias_VersionWeight AWS CloudFormation Resource (AWS::Lambda::Alias.VersionWeight)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-alias-versionweight.html
type AWSLambdaAlias_VersionWeight struct {

	// FunctionVersion AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-alias-versionweight.html#cfn-lambda-alias-versionweight-functionversion
	FunctionVersion string `json:"FunctionVersion,omitempty"`

	// FunctionWeight AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-alias-versionweight.html#cfn-lambda-alias-versionweight-functionweight
	FunctionWeight float64 `json:"FunctionWeight,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSLambdaAlias_VersionWeight) AWSCloudFormationType() string {
	return "AWS::Lambda::Alias.VersionWeight"
}
