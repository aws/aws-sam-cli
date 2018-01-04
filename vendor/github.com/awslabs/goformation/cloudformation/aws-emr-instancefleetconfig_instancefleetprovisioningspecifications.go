package cloudformation

// AWSEMRInstanceFleetConfig_InstanceFleetProvisioningSpecifications AWS CloudFormation Resource (AWS::EMR::InstanceFleetConfig.InstanceFleetProvisioningSpecifications)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-instancefleetprovisioningspecifications.html
type AWSEMRInstanceFleetConfig_InstanceFleetProvisioningSpecifications struct {

	// SpotSpecification AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancefleetconfig-instancefleetprovisioningspecifications.html#cfn-elasticmapreduce-instancefleetconfig-instancefleetprovisioningspecifications-spotspecification
	SpotSpecification *AWSEMRInstanceFleetConfig_SpotProvisioningSpecification `json:"SpotSpecification,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEMRInstanceFleetConfig_InstanceFleetProvisioningSpecifications) AWSCloudFormationType() string {
	return "AWS::EMR::InstanceFleetConfig.InstanceFleetProvisioningSpecifications"
}
