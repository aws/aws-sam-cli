package cloudformation

// AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.EncryptionConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-encryptionconfiguration.html
type AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration struct {

	// KMSEncryptionConfig AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-encryptionconfiguration.html#cfn-kinesisfirehose-deliverystream-encryptionconfiguration-kmsencryptionconfig
	KMSEncryptionConfig *AWSKinesisFirehoseDeliveryStream_KMSEncryptionConfig `json:"KMSEncryptionConfig,omitempty"`

	// NoEncryptionConfig AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-encryptionconfiguration.html#cfn-kinesisfirehose-deliverystream-encryptionconfiguration-noencryptionconfig
	NoEncryptionConfig string `json:"NoEncryptionConfig,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_EncryptionConfiguration) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.EncryptionConfiguration"
}
