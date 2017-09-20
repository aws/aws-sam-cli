package cloudformation

// AWSEMRCluster_EbsConfiguration AWS CloudFormation Resource (AWS::EMR::Cluster.EbsConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration.html
type AWSEMRCluster_EbsConfiguration struct {

	// EbsBlockDeviceConfigs AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration.html#cfn-emr-ebsconfiguration-ebsblockdeviceconfigs
	EbsBlockDeviceConfigs []AWSEMRCluster_EbsBlockDeviceConfig `json:"EbsBlockDeviceConfigs,omitempty"`

	// EbsOptimized AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration.html#cfn-emr-ebsconfiguration-ebsoptimized
	EbsOptimized bool `json:"EbsOptimized,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEMRCluster_EbsConfiguration) AWSCloudFormationType() string {
	return "AWS::EMR::Cluster.EbsConfiguration"
}
