package cloudformation

// AWSKinesisFirehoseDeliveryStream_ElasticsearchRetryOptions AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.ElasticsearchRetryOptions)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration-retryoptions.html
type AWSKinesisFirehoseDeliveryStream_ElasticsearchRetryOptions struct {

	// DurationInSeconds AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration-retryoptions.html#cfn-kinesisfirehose-kinesisdeliverystream-elasticsearchdestinationconfiguration-retryoptions-durationinseconds
	DurationInSeconds int `json:"DurationInSeconds,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_ElasticsearchRetryOptions) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.ElasticsearchRetryOptions"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisFirehoseDeliveryStream_ElasticsearchRetryOptions) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
