package cloudformation

// AWSKinesisAnalyticsApplication_RecordFormat AWS CloudFormation Resource (AWS::KinesisAnalytics::Application.RecordFormat)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-recordformat.html
type AWSKinesisAnalyticsApplication_RecordFormat struct {

	// MappingParameters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-recordformat.html#cfn-kinesisanalytics-application-recordformat-mappingparameters
	MappingParameters *AWSKinesisAnalyticsApplication_MappingParameters `json:"MappingParameters,omitempty"`

	// RecordFormatType AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-recordformat.html#cfn-kinesisanalytics-application-recordformat-recordformattype
	RecordFormatType string `json:"RecordFormatType,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisAnalyticsApplication_RecordFormat) AWSCloudFormationType() string {
	return "AWS::KinesisAnalytics::Application.RecordFormat"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisAnalyticsApplication_RecordFormat) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
