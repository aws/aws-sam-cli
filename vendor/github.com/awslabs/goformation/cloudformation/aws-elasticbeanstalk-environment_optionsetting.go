package cloudformation

// AWSElasticBeanstalkEnvironment_OptionSetting AWS CloudFormation Resource (AWS::ElasticBeanstalk::Environment.OptionSetting)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-option-settings.html
type AWSElasticBeanstalkEnvironment_OptionSetting struct {

	// Namespace AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-option-settings.html#cfn-beanstalk-optionsettings-namespace
	Namespace string `json:"Namespace,omitempty"`

	// OptionName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-option-settings.html#cfn-beanstalk-optionsettings-optionname
	OptionName string `json:"OptionName,omitempty"`

	// ResourceName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-option-settings.html#cfn-elasticbeanstalk-environment-optionsetting-resourcename
	ResourceName string `json:"ResourceName,omitempty"`

	// Value AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-option-settings.html#cfn-beanstalk-optionsettings-value
	Value string `json:"Value,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSElasticBeanstalkEnvironment_OptionSetting) AWSCloudFormationType() string {
	return "AWS::ElasticBeanstalk::Environment.OptionSetting"
}
