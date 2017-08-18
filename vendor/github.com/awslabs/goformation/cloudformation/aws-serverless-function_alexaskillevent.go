package cloudformation

// AWSServerlessFunction_AlexaSkillEvent AWS CloudFormation Resource (AWS::Serverless::Function.AlexaSkillEvent)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#alexaskill
type AWSServerlessFunction_AlexaSkillEvent struct {

	// Variables AWS CloudFormation Property
	// Required: false
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#alexaskill
	Variables map[string]string `json:"Variables,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_AlexaSkillEvent) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.AlexaSkillEvent"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSServerlessFunction_AlexaSkillEvent) AWSCloudFormationSpecificationVersion() string {
	return "2016-10-31"
}
