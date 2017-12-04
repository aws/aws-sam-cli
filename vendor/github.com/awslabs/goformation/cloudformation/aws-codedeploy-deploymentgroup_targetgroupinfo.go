package cloudformation

// AWSCodeDeployDeploymentGroup_TargetGroupInfo AWS CloudFormation Resource (AWS::CodeDeploy::DeploymentGroup.TargetGroupInfo)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-targetgroupinfo.html
type AWSCodeDeployDeploymentGroup_TargetGroupInfo struct {

	// Name AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-targetgroupinfo.html#cfn-codedeploy-deploymentgroup-targetgroupinfo-name
	Name string `json:"Name,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodeDeployDeploymentGroup_TargetGroupInfo) AWSCloudFormationType() string {
	return "AWS::CodeDeploy::DeploymentGroup.TargetGroupInfo"
}
