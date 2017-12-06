package cloudformation

// AWSS3Bucket_AbortIncompleteMultipartUpload AWS CloudFormation Resource (AWS::S3::Bucket.AbortIncompleteMultipartUpload)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-abortincompletemultipartupload.html
type AWSS3Bucket_AbortIncompleteMultipartUpload struct {

	// DaysAfterInitiation AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-abortincompletemultipartupload.html#cfn-s3-bucket-abortincompletemultipartupload-daysafterinitiation
	DaysAfterInitiation int `json:"DaysAfterInitiation,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_AbortIncompleteMultipartUpload) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.AbortIncompleteMultipartUpload"
}
