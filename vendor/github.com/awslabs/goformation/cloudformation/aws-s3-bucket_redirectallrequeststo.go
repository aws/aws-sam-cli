package cloudformation

// AWSS3Bucket_RedirectAllRequestsTo AWS CloudFormation Resource (AWS::S3::Bucket.RedirectAllRequestsTo)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-websiteconfiguration-redirectallrequeststo.html
type AWSS3Bucket_RedirectAllRequestsTo struct {

	// HostName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-websiteconfiguration-redirectallrequeststo.html#cfn-s3-websiteconfiguration-redirectallrequeststo-hostname
	HostName string `json:"HostName,omitempty"`

	// Protocol AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-websiteconfiguration-redirectallrequeststo.html#cfn-s3-websiteconfiguration-redirectallrequeststo-protocol
	Protocol string `json:"Protocol,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_RedirectAllRequestsTo) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.RedirectAllRequestsTo"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSS3Bucket_RedirectAllRequestsTo) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
