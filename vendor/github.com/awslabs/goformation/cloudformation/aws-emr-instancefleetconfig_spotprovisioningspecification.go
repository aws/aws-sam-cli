package cloudformation

// AWSEMRInstanceFleetConfig_SpotProvisioningSpecification AWS CloudFormation Resource (AWS::EMR::InstanceFleetConfig.SpotProvisioningSpecification)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-spotprovisioningspecification.html
type AWSEMRInstanceFleetConfig_SpotProvisioningSpecification struct {

	// BlockDurationMinutes AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-spotprovisioningspecification.html#cfn-elasticmapreduce-instancefleetconfig-spotprovisioningspecification-blockdurationminutes
	BlockDurationMinutes int `json:"BlockDurationMinutes,omitempty"`

	// TimeoutAction AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-spotprovisioningspecification.html#cfn-elasticmapreduce-instancefleetconfig-spotprovisioningspecification-timeoutaction
	TimeoutAction string `json:"TimeoutAction,omitempty"`

	// TimeoutDurationMinutes AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-spotprovisioningspecification.html#cfn-elasticmapreduce-instancefleetconfig-spotprovisioningspecification-timeoutdurationminutes
	TimeoutDurationMinutes int `json:"TimeoutDurationMinutes,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEMRInstanceFleetConfig_SpotProvisioningSpecification) AWSCloudFormationType() string {
	return "AWS::EMR::InstanceFleetConfig.SpotProvisioningSpecification"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSEMRInstanceFleetConfig_SpotProvisioningSpecification) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
