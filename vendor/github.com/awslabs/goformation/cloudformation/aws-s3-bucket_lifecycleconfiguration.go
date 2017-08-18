package cloudformation

// AWSS3Bucket_LifecycleConfiguration AWS CloudFormation Resource (AWS::S3::Bucket.LifecycleConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-lifecycleconfig.html
type AWSS3Bucket_LifecycleConfiguration struct {

	// Rules AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-lifecycleconfig.html#cfn-s3-bucket-lifecycleconfig-rules
	Rules []AWSS3Bucket_Rule `json:"Rules,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_LifecycleConfiguration) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.LifecycleConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSS3Bucket_LifecycleConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
