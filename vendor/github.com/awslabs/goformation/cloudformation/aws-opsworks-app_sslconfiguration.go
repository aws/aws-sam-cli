package cloudformation

// AWSOpsWorksApp_SslConfiguration AWS CloudFormation Resource (AWS::OpsWorks::App.SslConfiguration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-app-sslconfiguration.html
type AWSOpsWorksApp_SslConfiguration struct {

	// Certificate AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-app-sslconfiguration.html#cfn-opsworks-app-sslconfig-certificate
	Certificate string `json:"Certificate,omitempty"`

	// Chain AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-app-sslconfiguration.html#cfn-opsworks-app-sslconfig-chain
	Chain string `json:"Chain,omitempty"`

	// PrivateKey AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-app-sslconfiguration.html#cfn-opsworks-app-sslconfig-privatekey
	PrivateKey string `json:"PrivateKey,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSOpsWorksApp_SslConfiguration) AWSCloudFormationType() string {
	return "AWS::OpsWorks::App.SslConfiguration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSOpsWorksApp_SslConfiguration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
