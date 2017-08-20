package cloudformation

// AWSKinesisAnalyticsApplication_JSONMappingParameters AWS CloudFormation Resource (AWS::KinesisAnalytics::Application.JSONMappingParameters)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-jsonmappingparameters.html
type AWSKinesisAnalyticsApplication_JSONMappingParameters struct {

	// RecordRowPath AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisanalytics-application-jsonmappingparameters.html#cfn-kinesisanalytics-application-jsonmappingparameters-recordrowpath
	RecordRowPath string `json:"RecordRowPath,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSKinesisAnalyticsApplication_JSONMappingParameters) AWSCloudFormationType() string {
	return "AWS::KinesisAnalytics::Application.JSONMappingParameters"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSKinesisAnalyticsApplication_JSONMappingParameters) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
