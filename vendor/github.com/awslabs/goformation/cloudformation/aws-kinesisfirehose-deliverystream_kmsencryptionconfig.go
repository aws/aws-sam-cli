package cloudformation

// AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.KMSEncryptionConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration-kmsencryptionconfig.html
type AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig struct {

	// AWSKMSKeyARN AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration-kmsencryptionconfig.html#cfn-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration-kmsencryptionconfig-awskmskeyarn
	AWSKMSKeyARN string `json:"AWSKMSKeyARN,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.KMSEncryptionConfig"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
