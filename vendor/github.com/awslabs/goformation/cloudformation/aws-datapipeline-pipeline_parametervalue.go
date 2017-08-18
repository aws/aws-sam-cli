package cloudformation

// AWSDataPipelinePipeline_ParameterValue AWS CloudFormation Resource (AWS::DataPipeline::Pipeline.ParameterValue)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parametervalues.html
type AWSDataPipelinePipeline_ParameterValue struct {

	// Id AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parametervalues.html#cfn-datapipeline-pipeline-parametervalues-id
	Id string `json:"Id,omitempty"`

	// StringValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parametervalues.html#cfn-datapipeline-pipeline-parametervalues-stringvalue
	StringValue string `json:"StringValue,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSDataPipelinePipeline_ParameterValue) AWSCloudFormationType() string {
	return "AWS::DataPipeline::Pipeline.ParameterValue"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSDataPipelinePipeline_ParameterValue) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
