package cloudformation

// AWSECSService_PlacementStrategy AWS CloudFormation Resource (AWS::ECS::Service.PlacementStrategy)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html
type AWSECSService_PlacementStrategy struct {

	// Field AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html#cfn-ecs-service-placementstrategy-field
	Field string `json:"Field,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html#cfn-ecs-service-placementstrategy-type
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSECSService_PlacementStrategy) AWSCloudFormationType() string {
	return "AWS::ECS::Service.PlacementStrategy"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSECSService_PlacementStrategy) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
