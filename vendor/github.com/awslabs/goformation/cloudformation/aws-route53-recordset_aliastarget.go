package cloudformation

// AWSRoute53RecordSet_AliasTarget AWS CloudFormation Resource (AWS::Route53::RecordSet.AliasTarget)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-aliastarget.html
type AWSRoute53RecordSet_AliasTarget struct {

	// DNSName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-aliastarget.html#cfn-route53-aliastarget-dnshostname
	DNSName string `json:"DNSName,omitempty"`

	// EvaluateTargetHealth AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-aliastarget.html#cfn-route53-aliastarget-evaluatetargethealth
	EvaluateTargetHealth bool `json:"EvaluateTargetHealth,omitempty"`

	// HostedZoneId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-aliastarget.html#cfn-route53-aliastarget-hostedzoneid
	HostedZoneId string `json:"HostedZoneId,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSRoute53RecordSet_AliasTarget) AWSCloudFormationType() string {
	return "AWS::Route53::RecordSet.AliasTarget"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSRoute53RecordSet_AliasTarget) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
