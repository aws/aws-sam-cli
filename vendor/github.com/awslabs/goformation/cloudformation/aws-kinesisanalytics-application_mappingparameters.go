package cloudformation

// AWSKinesisAnalyticsApplication_MappingParameters AWS CloudFormation Resource (AWS::KinesisAnalytics::Application.MappingParameters)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-mappingparameters.html
type AWSKinesisAnalyticsApplication_MappingParameters struct {

	// CSVMappingParameters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-mappingparameters.html#cfn-kinesisanalytics-application-mappingparameters-csvmappingparameters
	CSVMappingParameters *AWSKinesisAnalyticsApplication_CSVMappingParameters `json:"CSVMappingParameters,omitempty"`

	// JSONMappingParameters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-mappingparameters.html#cfn-kinesisanalytics-application-mappingparameters-jsonmappingparameters
	JSONMappingParameters *AWSKinesisAnalyticsApplication_JSONMappingParameters `json:"JSONMappingParameters,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisAnalyticsApplication_MappingParameters) AWSCloudFormationType() string {
	return "AWS::KinesisAnalytics::Application.MappingParameters"
}
