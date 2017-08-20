package cloudformation

// AWSEMRInstanceGroupConfig_ScalingAction AWS CloudFormation Resource (AWS::EMR::InstanceGroupConfig.ScalingAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancegroupconfig-scalingaction.html
type AWSEMRInstanceGroupConfig_ScalingAction struct {

	// Market AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancegroupconfig-scalingaction.html#cfn-elasticmapreduce-instancegroupconfig-scalingaction-market
	Market string `json:"Market,omitempty"`

	// SimpleScalingPolicyConfiguration AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticmapreduce-instancegroupconfig-scalingaction.html#cfn-elasticmapreduce-instancegroupconfig-scalingaction-simplescalingpolicyconfiguration
	SimpleScalingPolicyConfiguration *AWSEMRInstanceGroupConfig_SimpleScalingPolicyConfiguration `json:"SimpleScalingPolicyConfiguration,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEMRInstanceGroupConfig_ScalingAction) AWSCloudFormationType() string {
	return "AWS::EMR::InstanceGroupConfig.ScalingAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSEMRInstanceGroupConfig_ScalingAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
