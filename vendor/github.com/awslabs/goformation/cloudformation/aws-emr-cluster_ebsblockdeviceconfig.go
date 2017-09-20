package cloudformation

// AWSEMRCluster_EbsBlockDeviceConfig AWS CloudFormation Resource (AWS::EMR::Cluster.EbsBlockDeviceConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration-ebsblockdeviceconfig.html
type AWSEMRCluster_EbsBlockDeviceConfig struct {

	// VolumeSpecification AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration-ebsblockdeviceconfig.html#cfn-emr-ebsconfiguration-ebsblockdeviceconfig-volumespecification
	VolumeSpecification *AWSEMRCluster_VolumeSpecification `json:"VolumeSpecification,omitempty"`

	// VolumesPerInstance AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-emr-ebsconfiguration-ebsblockdeviceconfig.html#cfn-emr-ebsconfiguration-ebsblockdeviceconfig-volumesperinstance
	VolumesPerInstance int `json:"VolumesPerInstance,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEMRCluster_EbsBlockDeviceConfig) AWSCloudFormationType() string {
	return "AWS::EMR::Cluster.EbsBlockDeviceConfig"
}
