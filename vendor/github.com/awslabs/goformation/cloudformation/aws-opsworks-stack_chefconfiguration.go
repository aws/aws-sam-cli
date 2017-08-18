package cloudformation

// AWSOpsWorksStack_ChefConfiguration AWS CloudFormation Resource (AWS::OpsWorks::Stack.ChefConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-chefconfiguration.html
type AWSOpsWorksStack_ChefConfiguration struct {

	// BerkshelfVersion AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-chefconfiguration.html#cfn-opsworks-chefconfiguration-berkshelfversion
	BerkshelfVersion string `json:"BerkshelfVersion,omitempty"`

	// ManageBerkshelf AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-chefconfiguration.html#cfn-opsworks-chefconfiguration-berkshelfversion
	ManageBerkshelf bool `json:"ManageBerkshelf,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSOpsWorksStack_ChefConfiguration) AWSCloudFormationType() string {
	return "AWS::OpsWorks::Stack.ChefConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSOpsWorksStack_ChefConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
