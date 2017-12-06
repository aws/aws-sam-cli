package cloudformation

// AWSS3Bucket_ReplicationDestination AWS CloudFormation Resource (AWS::S3::Bucket.ReplicationDestination)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-replicationconfiguration-rules-destination.html
type AWSS3Bucket_ReplicationDestination struct {

	// Bucket AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-replicationconfiguration-rules-destination.html#cfn-s3-bucket-replicationconfiguration-rules-destination-bucket
	Bucket string `json:"Bucket,omitempty"`

	// StorageClass AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-replicationconfiguration-rules-destination.html#cfn-s3-bucket-replicationconfiguration-rules-destination-storageclass
	StorageClass string `json:"StorageClass,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSS3Bucket_ReplicationDestination) AWSCloudFormationType() string {
	return "AWS::S3::Bucket.ReplicationDestination"
}
