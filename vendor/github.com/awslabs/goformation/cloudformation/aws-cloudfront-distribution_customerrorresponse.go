package cloudformation

// AWSCloudFrontDistribution_CustomErrorResponse AWS CloudFormation Resource (AWS::CloudFront::Distribution.CustomErrorResponse)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-customerrorresponse.html
type AWSCloudFrontDistribution_CustomErrorResponse struct {

	// ErrorCachingMinTTL AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-customerrorresponse.html#cfn-cloudfront-distributionconfig-customerrorresponse-errorcachingminttl
	ErrorCachingMinTTL int64 `json:"ErrorCachingMinTTL,omitempty"`

	// ErrorCode AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-customerrorresponse.html#cfn-cloudfront-distributionconfig-customerrorresponse-errorcode
	ErrorCode int `json:"ErrorCode,omitempty"`

	// ResponseCode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-customerrorresponse.html#cfn-cloudfront-distributionconfig-customerrorresponse-responsecode
	ResponseCode int `json:"ResponseCode,omitempty"`

	// ResponsePagePath AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distributionconfig-customerrorresponse.html#cfn-cloudfront-distributionconfig-customerrorresponse-responsepagepath
	ResponsePagePath string `json:"ResponsePagePath,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudFrontDistribution_CustomErrorResponse) AWSCloudFormationType() string {
	return "AWS::CloudFront::Distribution.CustomErrorResponse"
}
