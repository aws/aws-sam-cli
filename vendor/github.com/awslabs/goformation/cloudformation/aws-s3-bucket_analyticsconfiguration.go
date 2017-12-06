package cloudformation

// AWSS3Bucket_AnalyticsConfiguration AWS CloudFormation Resource (AWS::S3::Bucket.AnalyticsConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-analyticsconfiguration.html
type AWSS3Bucket_AnalyticsConfiguration struct {

	// Id AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-analyticsconfiguration.html#cfn-s3-bucket-analyticsconfiguration-id
	Id string `json:"Id,omitempty"`

	// Prefix AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-analyticsconfiguration.html#cfn-s3-bucket-analyticsconfiguration-prefix
	Prefix string `json:"Prefix,omitempty"`

	// StorageClassAnalysis AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-analyticsconfiguration.html#cfn-s3-bucket-analyticsconfiguration-storageclassanalysis
	StorageClassAnalysis *AWSS3Bucket_StorageClassAnalysis `json:"StorageClassAnalysis,omitempty"`

	// TagFilters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-analyticsconfiguration.html#cfn-s3-bucket-analyticsconfiguration-tagfilters
	TagFilters []AWSS3Bucket_TagFilter `json:"TagFilters,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_AnalyticsConfiguration) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.AnalyticsConfiguration"
}
