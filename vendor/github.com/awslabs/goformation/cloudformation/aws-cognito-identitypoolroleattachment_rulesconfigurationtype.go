package cloudformation

// AWSCognitoIdentityPoolRoleAttachment_RulesConfigurationType AWS CloudFormation Resource (AWS::Cognito::IdentityPoolRoleAttachment.RulesConfigurationType)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypoolroleattachment-rulesconfigurationtype.html
type AWSCognitoIdentityPoolRoleAttachment_RulesConfigurationType struct {
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCognitoIdentityPoolRoleAttachment_RulesConfigurationType) AWSCloudFormationType() string {
	return "AWS::Cognito::IdentityPoolRoleAttachment.RulesConfigurationType"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCognitoIdentityPoolRoleAttachment_RulesConfigurationType) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
