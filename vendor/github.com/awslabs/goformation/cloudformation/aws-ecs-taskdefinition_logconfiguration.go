package cloudformation

// AWSECSTaskDefinition_LogConfiguration AWS CloudFormation Resource (AWS::ECS::TaskDefinition.LogConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions-logconfiguration.html
type AWSECSTaskDefinition_LogConfiguration struct {

	// LogDriver AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions-logconfiguration.html#cfn-ecs-taskdefinition-containerdefinition-logconfiguration-logdriver
	LogDriver string `json:"LogDriver,omitempty"`

	// Options AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions-logconfiguration.html#cfn-ecs-taskdefinition-containerdefinition-logconfiguration-options
	Options map[string]string `json:"Options,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSECSTaskDefinition_LogConfiguration) AWSCloudFormationType() string {
	return "AWS::ECS::TaskDefinition.LogConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSECSTaskDefinition_LogConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
