package cloudformation

// AWSIoTTopicRule_DynamoDBAction AWS CloudFormation Resource (AWS::IoT::TopicRule.DynamoDBAction)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html
type AWSIoTTopicRule_DynamoDBAction struct {

	// HashKeyField AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-hashkeyfield
	HashKeyField string `json:"HashKeyField,omitempty"`

	// HashKeyValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-hashkeyvalue
	HashKeyValue string `json:"HashKeyValue,omitempty"`

	// PayloadField AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-payloadfield
	PayloadField string `json:"PayloadField,omitempty"`

	// RangeKeyField AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-rangekeyfield
	RangeKeyField string `json:"RangeKeyField,omitempty"`

	// RangeKeyValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-rangekeyvalue
	RangeKeyValue string `json:"RangeKeyValue,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// TableName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-iot-dynamodb.html#cfn-iot-dynamodb-tablename
	TableName string `json:"TableName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSIoTTopicRule_DynamoDBAction) AWSCloudFormationType() string {
	return "AWS::IoT::TopicRule.DynamoDBAction"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSIoTTopicRule_DynamoDBAction) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
