package cloudformation

// AWSCognitoIdentityPool_CognitoIdentityProvider AWS CloudFormation Resource (AWS::Cognito::IdentityPool.CognitoIdentityProvider)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitoidentityprovider.html
type AWSCognitoIdentityPool_CognitoIdentityProvider struct {

	// ClientId AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitoidentityprovider.html#cfn-cognito-identitypool-cognitoidentityprovider-clientid
	ClientId string `json:"ClientId,omitempty"`

	// ProviderName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitoidentityprovider.html#cfn-cognito-identitypool-cognitoidentityprovider-providername
	ProviderName string `json:"ProviderName,omitempty"`

	// ServerSideTokenCheck AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitoidentityprovider.html#cfn-cognito-identitypool-cognitoidentityprovider-serversidetokencheck
	ServerSideTokenCheck bool `json:"ServerSideTokenCheck,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCognitoIdentityPool_CognitoIdentityProvider) AWSCloudFormationType() string {
	return "AWS::Cognito::IdentityPool.CognitoIdentityProvider"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCognitoIdentityPool_CognitoIdentityProvider) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
