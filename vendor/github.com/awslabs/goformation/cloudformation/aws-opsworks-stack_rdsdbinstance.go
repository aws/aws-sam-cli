package cloudformation

// AWSOpsWorksStack_RdsDbInstance AWS CloudFormation Resource (AWS::OpsWorks::Stack.RdsDbInstance)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-rdsdbinstance.html
type AWSOpsWorksStack_RdsDbInstance struct {

	// DbPassword AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-rdsdbinstance.html#cfn-opsworks-stack-rdsdbinstance-dbpassword
	DbPassword string `json:"DbPassword,omitempty"`

	// DbUser AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-rdsdbinstance.html#cfn-opsworks-stack-rdsdbinstance-dbuser
	DbUser string `json:"DbUser,omitempty"`

	// RdsDbInstanceArn AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-opsworks-stack-rdsdbinstance.html#cfn-opsworks-stack-rdsdbinstance-rdsdbinstancearn
	RdsDbInstanceArn string `json:"RdsDbInstanceArn,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSOpsWorksStack_RdsDbInstance) AWSCloudFormationType() string {
	return "AWS::OpsWorks::Stack.RdsDbInstance"
}
