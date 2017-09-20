package cloudformation

// AWSCodeDeployDeploymentGroup_LoadBalancerInfo AWS CloudFormation Resource (AWS::CodeDeploy::DeploymentGroup.LoadBalancerInfo)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-loadbalancerinfo.html
type AWSCodeDeployDeploymentGroup_LoadBalancerInfo struct {

	// ElbInfoList AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codedeploy-deploymentgroup-loadbalancerinfo.html#cfn-codedeploy-deploymentgroup-loadbalancerinfo-elbinfolist
	ElbInfoList []AWSCodeDeployDeploymentGroup_ELBInfo `json:"ElbInfoList,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodeDeployDeploymentGroup_LoadBalancerInfo) AWSCloudFormationType() string {
	return "AWS::CodeDeploy::DeploymentGroup.LoadBalancerInfo"
}
