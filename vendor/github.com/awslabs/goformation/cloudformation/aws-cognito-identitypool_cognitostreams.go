package cloudformation

// AWSCognitoIdentityPool_CognitoStreams AWS CloudFormation Resource (AWS::Cognito::IdentityPool.CognitoStreams)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitostreams.html
type AWSCognitoIdentityPool_CognitoStreams struct {

	// RoleArn AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitostreams.html#cfn-cognito-identitypool-cognitostreams-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// StreamName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitostreams.html#cfn-cognito-identitypool-cognitostreams-streamname
	StreamName string `json:"StreamName,omitempty"`

	// StreamingStatus AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cognito-identitypool-cognitostreams.html#cfn-cognito-identitypool-cognitostreams-streamingstatus
	StreamingStatus string `json:"StreamingStatus,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCognitoIdentityPool_CognitoStreams) AWSCloudFormationType() string {
	return "AWS::Cognito::IdentityPool.CognitoStreams"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCognitoIdentityPool_CognitoStreams) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
