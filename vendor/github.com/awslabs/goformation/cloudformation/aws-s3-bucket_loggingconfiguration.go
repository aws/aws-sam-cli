package cloudformation

// AWSS3Bucket_LoggingConfiguration AWS CloudFormation Resource (AWS::S3::Bucket.LoggingConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-loggingconfig.html
type AWSS3Bucket_LoggingConfiguration struct {

	// DestinationBucketName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-loggingconfig.html#cfn-s3-bucket-loggingconfig-destinationbucketname
	DestinationBucketName string `json:"DestinationBucketName,omitempty"`

	// LogFilePrefix AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-loggingconfig.html#cfn-s3-bucket-loggingconfig-logfileprefix
	LogFilePrefix string `json:"LogFilePrefix,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_LoggingConfiguration) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.LoggingConfiguration"
}
