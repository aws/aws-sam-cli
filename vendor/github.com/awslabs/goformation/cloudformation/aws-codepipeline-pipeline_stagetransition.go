package cloudformation

// AWSCodePipelinePipeline_StageTransition AWS CloudFormation Resource (AWS::CodePipeline::Pipeline.StageTransition)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-disableinboundstagetransitions.html
type AWSCodePipelinePipeline_StageTransition struct {

	// Reason AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-disableinboundstagetransitions.html#cfn-codepipeline-pipeline-disableinboundstagetransitions-reason
	Reason string `json:"Reason,omitempty"`

	// StageName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-disableinboundstagetransitions.html#cfn-codepipeline-pipeline-disableinboundstagetransitions-stagename
	StageName string `json:"StageName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodePipelinePipeline_StageTransition) AWSCloudFormationType() string {
	return "AWS::CodePipeline::Pipeline.StageTransition"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCodePipelinePipeline_StageTransition) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
