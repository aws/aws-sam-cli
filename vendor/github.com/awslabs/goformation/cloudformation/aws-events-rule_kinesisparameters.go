package cloudformation

// AWSEventsRule_KinesisParameters AWS CloudFormation Resource (AWS::Events::Rule.KinesisParameters)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-events-rule-kinesisparameters.html
type AWSEventsRule_KinesisParameters struct {

	// PartitionKeyPath AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-events-rule-kinesisparameters.html#cfn-events-rule-kinesisparameters-partitionkeypath
	PartitionKeyPath string `json:"PartitionKeyPath,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEventsRule_KinesisParameters) AWSCloudFormationType() string {
	return "AWS::Events::Rule.KinesisParameters"
}
