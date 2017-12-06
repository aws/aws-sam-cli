package cloudformation

// AWSServerlessFunction_ScheduleEvent AWS CloudFormation Resource (AWS::Serverless::Function.ScheduleEvent)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#schedule
type AWSServerlessFunction_ScheduleEvent struct {

	// Input AWS CloudFormation Property
	// Required: false
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#schedule
	Input string `json:"Input,omitempty"`

	// Schedule AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#schedule
	Schedule string `json:"Schedule,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_ScheduleEvent) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.ScheduleEvent"
}
