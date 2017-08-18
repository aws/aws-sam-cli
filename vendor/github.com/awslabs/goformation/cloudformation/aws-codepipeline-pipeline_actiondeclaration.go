package cloudformation

// AWSCodePipelinePipeline_ActionDeclaration AWS CloudFormation Resource (AWS::CodePipeline::Pipeline.ActionDeclaration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html
type AWSCodePipelinePipeline_ActionDeclaration struct {

	// ActionTypeId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-actiontypeid
	ActionTypeId *AWSCodePipelinePipeline_ActionTypeId `json:"ActionTypeId,omitempty"`

	// Configuration AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-configuration
	Configuration interface{} `json:"Configuration,omitempty"`

	// InputArtifacts AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-inputartifacts
	InputArtifacts []AWSCodePipelinePipeline_InputArtifact `json:"InputArtifacts,omitempty"`

	// Name AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-name
	Name string `json:"Name,omitempty"`

	// OutputArtifacts AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-outputartifacts
	OutputArtifacts []AWSCodePipelinePipeline_OutputArtifact `json:"OutputArtifacts,omitempty"`

	// RoleArn AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-rolearn
	RoleArn string `json:"RoleArn,omitempty"`

	// RunOrder AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-pipeline-stages-actions.html#cfn-codepipeline-pipeline-stages-actions-runorder
	RunOrder int `json:"RunOrder,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCodePipelinePipeline_ActionDeclaration) AWSCloudFormationType() string {
	return "AWS::CodePipeline::Pipeline.ActionDeclaration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCodePipelinePipeline_ActionDeclaration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
