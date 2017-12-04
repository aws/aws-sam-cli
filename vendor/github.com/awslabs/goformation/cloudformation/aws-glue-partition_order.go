package cloudformation

// AWSGluePartition_Order AWS CloudFormation Resource (AWS::Glue::Partition.Order)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-partition-order.html
type AWSGluePartition_Order struct {

	// Column AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-partition-order.html#cfn-glue-partition-order-column
	Column string `json:"Column,omitempty"`

	// SortOrder AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-partition-order.html#cfn-glue-partition-order-sortorder
	SortOrder int `json:"SortOrder,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGluePartition_Order) AWSCloudFormationType() string {
	return "AWS::Glue::Partition.Order"
}
