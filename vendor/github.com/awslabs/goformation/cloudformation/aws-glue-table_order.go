package cloudformation

// AWSGlueTable_Order AWS CloudFormation Resource (AWS::Glue::Table.Order)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-table-order.html
type AWSGlueTable_Order struct {

	// Column AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-table-order.html#cfn-glue-table-order-column
	Column string `json:"Column,omitempty"`

	// SortOrder AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-table-order.html#cfn-glue-table-order-sortorder
	SortOrder int `json:"SortOrder,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueTable_Order) AWSCloudFormationType() string {
	return "AWS::Glue::Table.Order"
}
