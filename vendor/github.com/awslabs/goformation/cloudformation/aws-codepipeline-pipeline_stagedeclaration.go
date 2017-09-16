package cloudformation

// AWSCodePipelinePipeline_StageDeclaration AWS CloudFormation Resource (AWS::CodePipeline::Pipeline.StageDeclaration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages.html
type AWSCodePipelinePipeline_StageDeclaration struct {

	// Actions AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages.html#cfn-codepipeline-pipeline-stages-actions
	Actions []AWSCodePipelinePipeline_ActionDeclaration `json:"Actions,omitempty"`

	// Blockers AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages.html#cfn-codepipeline-pipeline-stages-blockers
	Blockers []AWSCodePipelinePipeline_BlockerDeclaration `json:"Blockers,omitempty"`

	// Name AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages.html#cfn-codepipeline-pipeline-stages-name
	Name string `json:"Name,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodePipelinePipeline_StageDeclaration) AWSCloudFormationType() string {
	return "AWS::CodePipeline::Pipeline.StageDeclaration"
}
