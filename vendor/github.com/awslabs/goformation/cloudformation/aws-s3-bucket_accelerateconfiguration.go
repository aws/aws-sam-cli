package cloudformation

// AWSS3Bucket_AccelerateConfiguration AWS CloudFormation Resource (AWS::S3::Bucket.AccelerateConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-accelerateconfiguration.html
type AWSS3Bucket_AccelerateConfiguration struct {

	// AccelerationStatus AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-accelerateconfiguration.html#cfn-s3-bucket-accelerateconfiguration-accelerationstatus
	AccelerationStatus string `json:"AccelerationStatus,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_AccelerateConfiguration) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.AccelerateConfiguration"
}
