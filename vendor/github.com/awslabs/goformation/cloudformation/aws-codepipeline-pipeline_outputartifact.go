package cloudformation

// AWSCodePipelinePipeline_OutputArtifact AWS CloudFormation Resource (AWS::CodePipeline::Pipeline.OutputArtifact)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions-outputartifacts.html
type AWSCodePipelinePipeline_OutputArtifact struct {

	// Name AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions-outputartifacts.html#cfn-codepipeline-pipeline-stages-actions-outputartifacts-name
	Name string `json:"Name,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodePipelinePipeline_OutputArtifact) AWSCloudFormationType() string {
	return "AWS::CodePipeline::Pipeline.OutputArtifact"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCodePipelinePipeline_OutputArtifact) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
