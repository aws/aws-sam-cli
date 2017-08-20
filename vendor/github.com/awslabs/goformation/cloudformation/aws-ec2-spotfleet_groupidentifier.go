package cloudformation

// AWSEC2SpotFleet_GroupIdentifier AWS CloudFormation Resource (AWS::EC2::SpotFleet.GroupIdentifier)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata-launchspecifications-securitygroups.html
type AWSEC2SpotFleet_GroupIdentifier struct {

	// GroupId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata-launchspecifications-securitygroups.html#cfn-ec2-spotfleet-groupidentifier-groupid
	GroupId string `json:"GroupId,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEC2SpotFleet_GroupIdentifier) AWSCloudFormationType() string {
	return "AWS::EC2::SpotFleet.GroupIdentifier"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSEC2SpotFleet_GroupIdentifier) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
