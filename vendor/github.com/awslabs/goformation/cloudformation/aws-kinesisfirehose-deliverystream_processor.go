package cloudformation

// AWSKinesisFirehoseDeliveryStream_Processor AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.Processor)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-processor.html
type AWSKinesisFirehoseDeliveryStream_Processor struct {

	// Parameters AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-processor.html#cfn-kinesisfirehose-deliverystream-processor-parameters
	Parameters []AWSKinesisFirehoseDeliveryStream_ProcessorParameter `json:"Parameters,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-processor.html#cfn-kinesisfirehose-deliverystream-processor-type
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_Processor) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.Processor"
}
