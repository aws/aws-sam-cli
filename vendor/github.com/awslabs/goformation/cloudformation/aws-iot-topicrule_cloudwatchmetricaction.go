package cloudformation

// AWSIoTTopicRule_CloudwatchMetricAction AWS CloudFormation Resource (AWS::IoT::TopicRule.CloudwatchMetricAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html
type AWSIoTTopicRule_CloudwatchMetricAction struct {

	// MetricName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-metricname
	MetricName string `json:"MetricName,omitempty"`

	// MetricNamespace AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-metricnamespace
	MetricNamespace string `json:"MetricNamespace,omitempty"`

	// MetricTimestamp AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-metrictimestamp
	MetricTimestamp string `json:"MetricTimestamp,omitempty"`

	// MetricUnit AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-metricunit
	MetricUnit string `json:"MetricUnit,omitempty"`

	// MetricValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-metricvalue
	MetricValue string `json:"MetricValue,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-cloudwatchmetric.html#cfn-iot-cloudwatchmetric-rolearn
	RoleArn string `json:"RoleArn,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_CloudwatchMetricAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.CloudwatchMetricAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_CloudwatchMetricAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
