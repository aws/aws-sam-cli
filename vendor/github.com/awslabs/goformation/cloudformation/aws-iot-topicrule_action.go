package cloudformation

// AWSIoTTopicRule_Action AWS CloudFormation Resource (AWS::IoT::TopicRule.Action)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html
type AWSIoTTopicRule_Action struct {

	// CloudwatchAlarm AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-cloudwatchalarm
	CloudwatchAlarm *AWSIoTTopicRule_CloudwatchAlarmAction `json:"CloudwatchAlarm,omitempty"`

	// CloudwatchMetric AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-cloudwatchmetric
	CloudwatchMetric *AWSIoTTopicRule_CloudwatchMetricAction `json:"CloudwatchMetric,omitempty"`

	// DynamoDB AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-dynamodb
	DynamoDB *AWSIoTTopicRule_DynamoDBAction `json:"DynamoDB,omitempty"`

	// Elasticsearch AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-elasticsearch
	Elasticsearch *AWSIoTTopicRule_ElasticsearchAction `json:"Elasticsearch,omitempty"`

	// Firehose AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-firehose
	Firehose *AWSIoTTopicRule_FirehoseAction `json:"Firehose,omitempty"`

	// Kinesis AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-kinesis
	Kinesis *AWSIoTTopicRule_KinesisAction `json:"Kinesis,omitempty"`

	// Lambda AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-lambda
	Lambda *AWSIoTTopicRule_LambdaAction `json:"Lambda,omitempty"`

	// Republish AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-republish
	Republish *AWSIoTTopicRule_RepublishAction `json:"Republish,omitempty"`

	// S3 AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-s3
	S3 *AWSIoTTopicRule_S3Action `json:"S3,omitempty"`

	// Sns AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-sns
	Sns *AWSIoTTopicRule_SnsAction `json:"Sns,omitempty"`

	// Sqs AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-actions.html#cfn-iot-action-sqs
	Sqs *AWSIoTTopicRule_SqsAction `json:"Sqs,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_Action) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.Action"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_Action) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
