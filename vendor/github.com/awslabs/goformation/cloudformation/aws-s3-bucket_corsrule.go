package cloudformation

// AWSS3Bucket_CorsRule AWS CloudFormation Resource (AWS::S3::Bucket.CorsRule)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html
type AWSS3Bucket_CorsRule struct {

	// AllowedHeaders AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-allowedheaders
	AllowedHeaders []string `json:"AllowedHeaders,omitempty"`

	// AllowedMethods AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-allowedmethods
	AllowedMethods []string `json:"AllowedMethods,omitempty"`

	// AllowedOrigins AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-allowedorigins
	AllowedOrigins []string `json:"AllowedOrigins,omitempty"`

	// ExposedHeaders AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-exposedheaders
	ExposedHeaders []string `json:"ExposedHeaders,omitempty"`

	// Id AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-id
	Id string `json:"Id,omitempty"`

	// MaxAge AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-cors-corsrule.html#cfn-s3-bucket-cors-corsrule-maxage
	MaxAge int `json:"MaxAge,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_CorsRule) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.CorsRule"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSS3Bucket_CorsRule) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
