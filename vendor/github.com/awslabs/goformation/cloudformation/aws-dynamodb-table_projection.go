package cloudformation

// AWSDynamoDBTable_Projection AWS CloudFormation Resource (AWS::DynamoDB::Table.Projection)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-projectionobject.html
type AWSDynamoDBTable_Projection struct {

	// NonKeyAttributes AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-projectionobject.html#cfn-dynamodb-projectionobj-nonkeyatt
	NonKeyAttributes []string `json:"NonKeyAttributes,omitempty"`

	// ProjectionType AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-dynamodb-projectionobject.html#cfn-dynamodb-projectionobj-projtype
	ProjectionType string `json:"ProjectionType,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSDynamoDBTable_Projection) AWSCloudFormationType() string {
	return "AWS::DynamoDB::Table.Projection"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSDynamoDBTable_Projection) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
