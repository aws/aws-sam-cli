package cloudformation

// AWSCloudFrontDistribution_S3OriginConfig AWS CloudFormation Resource (AWS::CloudFront::Distribution.S3OriginConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-s3origin.html
type AWSCloudFrontDistribution_S3OriginConfig struct {

	// OriginAccessIdentity AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-s3origin.html#cfn-cloudfront-s3origin-originaccessidentity
	OriginAccessIdentity string `json:"OriginAccessIdentity,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudFrontDistribution_S3OriginConfig) AWSCloudFormationType() string {
	return "AWS::CloudFront::Distribution.S3OriginConfig"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCloudFrontDistribution_S3OriginConfig) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
