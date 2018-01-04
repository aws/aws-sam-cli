package cloudformation

// AWSServerlessSimpleTable_ProvisionedThroughput AWS CloudFormation Resource (AWS::Serverless::SimpleTable.ProvisionedThroughput)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html
type AWSServerlessSimpleTable_ProvisionedThroughput struct {

	// ReadCapacityUnits AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html
	ReadCapacityUnits int `json:"ReadCapacityUnits,omitempty"`

	// WriteCapacityUnits AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-provisionedthroughput.html
	WriteCapacityUnits int `json:"WriteCapacityUnits,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessSimpleTable_ProvisionedThroughput) AWSCloudFormationType() string {
	return "AWS::Serverless::SimpleTable.ProvisionedThroughput"
}
