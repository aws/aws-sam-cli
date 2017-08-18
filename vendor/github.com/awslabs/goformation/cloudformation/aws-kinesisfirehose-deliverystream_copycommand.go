package cloudformation

// AWSKinesisFirehoseDeliveryStream_CopyCommand AWS CloudFormation Resource (AWS::KinesisFirehose::DeliveryStream.CopyCommand)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand.html
type AWSKinesisFirehoseDeliveryStream_CopyCommand struct {

	// CopyOptions AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand.html#cfn-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand-copyoptions
	CopyOptions string `json:"CopyOptions,omitempty"`

	// DataTableColumns AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand.html#cfn-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand-datatablecolumns
	DataTableColumns string `json:"DataTableColumns,omitempty"`

	// DataTableName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand.html#cfn-kinesisfirehose-kinesisdeliverystream-redshiftdestinationconfiguration-copycommand-datatablename
	DataTableName string `json:"DataTableName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisFirehoseDeliveryStream_CopyCommand) AWSCloudFormationType() string {
	return "AWS::KinesisFirehose::DeliveryStream.CopyCommand"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisFirehoseDeliveryStream_CopyCommand) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
