package cloudformation

// AWSOpsWorksStack_StackConfigurationManager AWS CloudFormation Resource (AWS::OpsWorks::Stack.StackConfigurationManager)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-stackconfigmanager.html
type AWSOpsWorksStack_StackConfigurationManager struct {

	// Name AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-stackconfigmanager.html#cfn-opsworks-configmanager-name
	Name string `json:"Name,omitempty"`

	// Version AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-stackconfigmanager.html#cfn-opsworks-configmanager-version
	Version string `json:"Version,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSOpsWorksStack_StackConfigurationManager) AWSCloudFormationType() string {
	return "AWS::OpsWorks::Stack.StackConfigurationManager"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSOpsWorksStack_StackConfigurationManager) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
