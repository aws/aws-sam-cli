package cloudformation

// AWSCloudFrontDistribution_OriginCustomHeader AWS CloudFormation Resource (AWS::CloudFront::Distribution.OriginCustomHeader)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-origin-origincustomheader.html
type AWSCloudFrontDistribution_OriginCustomHeader struct {

	// HeaderName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-origin-origincustomheader.html#cfn-cloudfront-origin-origincustomheader-headername
	HeaderName string `json:"HeaderName,omitempty"`

	// HeaderValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-origin-origincustomheader.html#cfn-cloudfront-origin-origincustomheader-headervalue
	HeaderValue string `json:"HeaderValue,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudFrontDistribution_OriginCustomHeader) AWSCloudFormationType() string {
	return "AWS::CloudFront::Distribution.OriginCustomHeader"
}
