package cloudformation

// AWSCloudFrontDistribution_Restrictions AWS CloudFormation Resource (AWS::CloudFront::Distribution.Restrictions)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-restrictions.html
type AWSCloudFrontDistribution_Restrictions struct {

	// GeoRestriction AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-restrictions.html#cfn-cloudfront-distributionconfig-restrictions-georestriction
	GeoRestriction *AWSCloudFrontDistribution_GeoRestriction `json:"GeoRestriction,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudFrontDistribution_Restrictions) AWSCloudFormationType() string {
	return "AWS::CloudFront::Distribution.Restrictions"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCloudFrontDistribution_Restrictions) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
