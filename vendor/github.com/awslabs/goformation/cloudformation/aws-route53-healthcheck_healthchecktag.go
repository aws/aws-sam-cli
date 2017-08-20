package cloudformation

// AWSRoute53HealthCheck_HealthCheckTag AWS CloudFormation Resource (AWS::Route53::HealthCheck.HealthCheckTag)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-healthcheck-healthchecktag.html
type AWSRoute53HealthCheck_HealthCheckTag struct {

	// Key AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-healthcheck-healthchecktag.html#cfn-route53-healthchecktags-key
	Key string `json:"Key,omitempty"`

	// Value AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-healthcheck-healthchecktag.html#cfn-route53-healthchecktags-value
	Value string `json:"Value,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSRoute53HealthCheck_HealthCheckTag) AWSCloudFormationType() string {
	return "AWS::Route53::HealthCheck.HealthCheckTag"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSRoute53HealthCheck_HealthCheckTag) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
