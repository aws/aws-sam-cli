package cloudformation

// AWSCodeBuildProject_SourceAuth AWS CloudFormation Resource (AWS::CodeBuild::Project.SourceAuth)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-sourceauth.html
type AWSCodeBuildProject_SourceAuth struct {

	// Resource AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-sourceauth.html#cfn-codebuild-project-sourceauth-resource
	Resource string `json:"Resource,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-sourceauth.html#cfn-codebuild-project-sourceauth-type
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodeBuildProject_SourceAuth) AWSCloudFormationType() string {
	return "AWS::CodeBuild::Project.SourceAuth"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCodeBuildProject_SourceAuth) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
