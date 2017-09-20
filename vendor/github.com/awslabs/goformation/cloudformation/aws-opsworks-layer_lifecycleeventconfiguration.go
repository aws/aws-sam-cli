package cloudformation

// AWSOpsWorksLayer_LifecycleEventConfiguration AWS CloudFormation Resource (AWS::OpsWorks::Layer.LifecycleEventConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-layer-lifecycleeventconfiguration.html
type AWSOpsWorksLayer_LifecycleEventConfiguration struct {

	// ShutdownEventConfiguration AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-layer-lifecycleeventconfiguration.html#cfn-opsworks-layer-lifecycleconfiguration-shutdowneventconfiguration
	ShutdownEventConfiguration *AWSOpsWorksLayer_ShutdownEventConfiguration `json:"ShutdownEventConfiguration,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSOpsWorksLayer_LifecycleEventConfiguration) AWSCloudFormationType() string {
	return "AWS::OpsWorks::Layer.LifecycleEventConfiguration"
}
