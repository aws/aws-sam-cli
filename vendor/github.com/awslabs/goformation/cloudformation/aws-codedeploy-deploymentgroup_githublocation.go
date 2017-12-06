package cloudformation

// AWSCodeDeployDeploymentGroup_GitHubLocation AWS CloudFormation Resource (AWS::CodeDeploy::DeploymentGroup.GitHubLocation)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-deployment-revision-githublocation.html
type AWSCodeDeployDeploymentGroup_GitHubLocation struct {

	// CommitId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-deployment-revision-githublocation.html#cfn-properties-codedeploy-deploymentgroup-deployment-revision-githublocation-commitid
	CommitId string `json:"CommitId,omitempty"`

	// Repository AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-deployment-revision-githublocation.html#cfn-properties-codedeploy-deploymentgroup-deployment-revision-githublocation-repository
	Repository string `json:"Repository,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodeDeployDeploymentGroup_GitHubLocation) AWSCloudFormationType() string {
	return "AWS::CodeDeploy::DeploymentGroup.GitHubLocation"
}
