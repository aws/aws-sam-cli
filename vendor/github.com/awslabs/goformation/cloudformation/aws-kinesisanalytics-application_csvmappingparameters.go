package cloudformation

// AWSKinesisAnalyticsApplication_CSVMappingParameters AWS CloudFormation Resource (AWS::KinesisAnalytics::Application.CSVMappingParameters)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-csvmappingparameters.html
type AWSKinesisAnalyticsApplication_CSVMappingParameters struct {

	// RecordColumnDelimiter AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-csvmappingparameters.html#cfn-kinesisanalytics-application-csvmappingparameters-recordcolumndelimiter
	RecordColumnDelimiter string `json:"RecordColumnDelimiter,omitempty"`

	// RecordRowDelimiter AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-csvmappingparameters.html#cfn-kinesisanalytics-application-csvmappingparameters-recordrowdelimiter
	RecordRowDelimiter string `json:"RecordRowDelimiter,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisAnalyticsApplication_CSVMappingParameters) AWSCloudFormationType() string {
	return "AWS::KinesisAnalytics::Application.CSVMappingParameters"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisAnalyticsApplication_CSVMappingParameters) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
