package cloudformation

// AWSS3Bucket_StorageClassAnalysis AWS CloudFormation Resource (AWS::S3::Bucket.StorageClassAnalysis)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-storageclassanalysis.html
type AWSS3Bucket_StorageClassAnalysis struct {

	// DataExport AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-storageclassanalysis.html#cfn-s3-bucket-storageclassanalysis-dataexport
	DataExport *AWSS3Bucket_DataExport `json:"DataExport,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_StorageClassAnalysis) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.StorageClassAnalysis"
}
