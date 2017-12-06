package cloudformation

// AWSEC2SpotFleet_PrivateIpAddressSpecification AWS CloudFormation Resource (AWS::EC2::SpotFleet.PrivateIpAddressSpecification)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata-launchspecifications-networkinterfaces-privateipaddresses.html
type AWSEC2SpotFleet_PrivateIpAddressSpecification struct {

	// Primary AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata-launchspecifications-networkinterfaces-privateipaddresses.html#cfn-ec2-spotfleet-privateipaddressspecification-primary
	Primary bool `json:"Primary,omitempty"`

	// PrivateIpAddress AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata-launchspecifications-networkinterfaces-privateipaddresses.html#cfn-ec2-spotfleet-privateipaddressspecification-privateipaddress
	PrivateIpAddress string `json:"PrivateIpAddress,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEC2SpotFleet_PrivateIpAddressSpecification) AWSCloudFormationType() string {
	return "AWS::EC2::SpotFleet.PrivateIpAddressSpecification"
}
