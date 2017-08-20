package cloudformation

// AWSRoute53HostedZone_VPC AWS CloudFormation Resource (AWS::Route53::HostedZone.VPC)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone-hostedzonevpcs.html
type AWSRoute53HostedZone_VPC struct {

	// VPCId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone-hostedzonevpcs.html#cfn-route53-hostedzone-hostedzonevpcs-vpcid
	VPCId string `json:"VPCId,omitempty"`

	// VPCRegion AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone-hostedzonevpcs.html#cfn-route53-hostedzone-hostedzonevpcs-vpcregion
	VPCRegion string `json:"VPCRegion,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSRoute53HostedZone_VPC) AWSCloudFormationType() string {
	return "AWS::Route53::HostedZone.VPC"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSRoute53HostedZone_VPC) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
