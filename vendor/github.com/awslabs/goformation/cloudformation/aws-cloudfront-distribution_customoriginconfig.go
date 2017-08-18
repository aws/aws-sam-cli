package cloudformation

// AWSCloudFrontDistribution_CustomOriginConfig AWS CloudFormation Resource (AWS::CloudFront::Distribution.CustomOriginConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-customorigin.html
type AWSCloudFrontDistribution_CustomOriginConfig struct {

	// HTTPPort AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-customorigin.html#cfn-cloudfront-customorigin-httpport
	HTTPPort int `json:"HTTPPort,omitempty"`

	// HTTPSPort AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-customorigin.html#cfn-cloudfront-customorigin-httpsport
	HTTPSPort int `json:"HTTPSPort,omitempty"`

	// OriginProtocolPolicy AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-customorigin.html#cfn-cloudfront-customorigin-originprotocolpolicy
	OriginProtocolPolicy string `json:"OriginProtocolPolicy,omitempty"`

	// OriginSSLProtocols AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-customorigin.html#cfn-cloudfront-customorigin-originsslprotocols
	OriginSSLProtocols []string `json:"OriginSSLProtocols,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudFrontDistribution_CustomOriginConfig) AWSCloudFormationType() string {
	return "AWS::CloudFront::Distribution.CustomOriginConfig"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCloudFrontDistribution_CustomOriginConfig) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
