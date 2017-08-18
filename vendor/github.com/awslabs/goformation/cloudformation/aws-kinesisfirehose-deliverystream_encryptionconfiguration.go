package cloudformation

// AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.EncryptionConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration.html
type AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration struct {

	// KMSEncryptionConfig AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration.html#cfn-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration-kmsencryptionconfig
	KMSEncryptionConfig *AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig `json:"KMSEncryptionConfig,omitempty"`

	// NoEncryptionConfig AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration.html#cfn-kinesisfirehose-kinesisdeliverystream-s3destinationconfiguration-encryptionconfiguration-noencryptionconfig
	NoEncryptionConfig string `json:"NoEncryptionConfig,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.EncryptionConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
