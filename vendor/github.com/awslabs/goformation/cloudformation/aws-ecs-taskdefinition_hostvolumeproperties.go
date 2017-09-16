package cloudformation

// AWSECSTaskDefinition_HostVolumeProperties AWS CloudFormation Resource (AWS::ECS::TaskDefinition.HostVolumeProperties)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-volumes-host.html
type AWSECSTaskDefinition_HostVolumeProperties struct {

	// SourcePath AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-volumes-host.html#cfn-ecs-taskdefinition-volumes-host-sourcepath
	SourcePath string `json:"SourcePath,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSECSTaskDefinition_HostVolumeProperties) AWSCloudFormationType() string {
	return "AWS::ECS::TaskDefinition.HostVolumeProperties"
}
