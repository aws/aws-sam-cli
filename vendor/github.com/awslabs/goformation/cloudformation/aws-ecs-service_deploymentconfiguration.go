package cloudformation

// AWSECSService_DeploymentConfiguration AWS CloudFormation Resource (AWS::ECS::Service.DeploymentConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-deploymentconfiguration.html
type AWSECSService_DeploymentConfiguration struct {

	// MaximumPercent AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-deploymentconfiguration.html#cfn-ecs-service-deploymentconfiguration-maximumpercent
	MaximumPercent int `json:"MaximumPercent,omitempty"`

	// MinimumHealthyPercent AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-deploymentconfiguration.html#cfn-ecs-service-deploymentconfiguration-minimumhealthypercent
	MinimumHealthyPercent int `json:"MinimumHealthyPercent,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSECSService_DeploymentConfiguration) AWSCloudFormationType() string {
	return "AWS::ECS::Service.DeploymentConfiguration"
}
