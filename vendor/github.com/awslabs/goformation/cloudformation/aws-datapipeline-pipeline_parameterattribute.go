package cloudformation

// AWSDataPipelinePipeline_ParameterAttribute AWS CloudFormation Resource (AWS::DataPipeline::Pipeline.ParameterAttribute)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parameterobjects-attributes.html
type AWSDataPipelinePipeline_ParameterAttribute struct {

	// Key AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parameterobjects-attributes.html#cfn-datapipeline-pipeline-parameterobjects-attribtues-key
	Key string `json:"Key,omitempty"`

	// StringValue AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-datapipeline-pipeline-parameterobjects-attributes.html#cfn-datapipeline-pipeline-parameterobjects-attribtues-stringvalue
	StringValue string `json:"StringValue,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSDataPipelinePipeline_ParameterAttribute) AWSCloudFormationType() string {
	return "AWS::DataPipeline::Pipeline.ParameterAttribute"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSDataPipelinePipeline_ParameterAttribute) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
