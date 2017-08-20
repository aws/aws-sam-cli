package cloudformation

// AWSKinesisFirehoseDeliveryStream_ElasticsearchBufferingHints AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.ElasticsearchBufferingHints)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration.html
type AWSKinesisFirehoseDeliveryStream_ElasticsearchBufferingHints struct {

	// IntervalInSeconds AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration.html#cfn-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration-bufferinghints-intervalinseconds
	IntervalInSeconds int `json:"IntervalInSeconds,omitempty"`

	// SizeInMBs AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration.html#cfn-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration-bufferinghints-sizeinmbs
	SizeInMBs int `json:"SizeInMBs,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_ElasticsearchBufferingHints) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.ElasticsearchBufferingHints"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisFirehoseDeliveryStream_ElasticsearchBufferingHints) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
