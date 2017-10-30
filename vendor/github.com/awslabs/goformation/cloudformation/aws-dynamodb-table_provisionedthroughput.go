package cloudformation

// AWSDynamoDBTable_ProvisionedThroughput AWS CloudFormation Resource (AWS::DynamoDB::Table.ProvisionedThroughput)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html
type AWSDynamoDBTable_ProvisionedThroughput struct {

	// ReadCapacityUnits AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html#cfn-dynamodb-provisionedthroughput-readcapacityunits
	ReadCapacityUnits int64 `json:"ReadCapacityUnits,omitempty"`

	// WriteCapacityUnits AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html#cfn-dynamodb-provisionedthroughput-writecapacityunits
	WriteCapacityUnits int64 `json:"WriteCapacityUnits,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSDynamoDBTable_ProvisionedThroughput) AWSCloudFormationType() string {
	return "AWS::DynamoDB::Table.ProvisionedThroughput"
}
