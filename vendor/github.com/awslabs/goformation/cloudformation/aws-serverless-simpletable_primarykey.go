package cloudformation

// AWSServerlessSimpleTable_PrimaryKey AWS CloudFormation Resource (AWS::Serverless::SimpleTable.PrimaryKey)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#primary-key-object
type AWSServerlessSimpleTable_PrimaryKey struct {

	// Name AWS CloudFormation Property
	// Required: false
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#primary-key-object
	Name string `json:"Name,omitempty"`

	// Type AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#primary-key-object
	Type string `json:"Type,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessSimpleTable_PrimaryKey) AWSCloudFormationType() string {
	return "AWS::Serverless::SimpleTable.PrimaryKey"
}
