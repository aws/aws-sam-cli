package cloudformation

// AWSElasticBeanstalkApplication_ApplicationVersionLifecycleConfig AWS CloudFormation Resource (AWS::ElasticBeanstalk::Application.ApplicationVersionLifecycleConfig)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticbeanstalk-application-applicationversionlifecycleconfig.html
type AWSElasticBeanstalkApplication_ApplicationVersionLifecycleConfig struct {

	// MaxAgeRule AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticbeanstalk-application-applicationversionlifecycleconfig.html#cfn-elasticbeanstalk-application-applicationversionlifecycleconfig-maxagerule
	MaxAgeRule *AWSElasticBeanstalkApplication_MaxAgeRule `json:"MaxAgeRule,omitempty"`

	// MaxCountRule AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticbeanstalk-application-applicationversionlifecycleconfig.html#cfn-elasticbeanstalk-application-applicationversionlifecycleconfig-maxcountrule
	MaxCountRule *AWSElasticBeanstalkApplication_MaxCountRule `json:"MaxCountRule,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSElasticBeanstalkApplication_ApplicationVersionLifecycleConfig) AWSCloudFormationType() string {
	return "AWS::ElasticBeanstalk::Application.ApplicationVersionLifecycleConfig"
}
