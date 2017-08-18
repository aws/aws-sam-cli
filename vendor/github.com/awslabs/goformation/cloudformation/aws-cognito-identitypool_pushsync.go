package cloudformation

// AWSCognitoIdentityPool_PushSync AWS CloudFormation Resource (AWS::Cognito::IdentityPool.PushSync)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-pushsync.html
type AWSCognitoIdentityPool_PushSync struct {

	// ApplicationArns AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-pushsync.html#cfn-cognito-identitypool-pushsync-applicationarns
	ApplicationArns []string `json:"ApplicationArns,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-pushsync.html#cfn-cognito-identitypool-pushsync-rolearn
	RoleArn string `json:"RoleArn,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCognitoIdentityPool_PushSync) AWSCloudFormationType() string {
	return "AWS::Cognito::IdentityPool.PushSync"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCognitoIdentityPool_PushSync) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
