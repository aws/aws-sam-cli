package cloudformation

// AWSDirectoryServiceMicrosoftAD_VpcSettings AWS CloudFormation Resource (AWS::DirectoryService::MicrosoftAD.VpcSettings)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-directoryservice-microsoftad-vpcsettings.html
type AWSDirectoryServiceMicrosoftAD_VpcSettings struct {

	// SubnetIds AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-directoryservice-microsoftad-vpcsettings.html#cfn-directoryservice-microsoftad-vpcsettings-subnetids
	SubnetIds []string `json:"SubnetIds,omitempty"`

	// VpcId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-directoryservice-microsoftad-vpcsettings.html#cfn-directoryservice-microsoftad-vpcsettings-vpcid
	VpcId string `json:"VpcId,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSDirectoryServiceMicrosoftAD_VpcSettings) AWSCloudFormationType() string {
	return "AWS::DirectoryService::MicrosoftAD.VpcSettings"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSDirectoryServiceMicrosoftAD_VpcSettings) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
