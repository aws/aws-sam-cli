package cloudformation

// AWSGlueJob_ExecutionProperty AWS CloudFormation Resource (AWS::Glue::Job.ExecutionProperty)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-job-executionproperty.html
type AWSGlueJob_ExecutionProperty struct {

	// MaxConcurrentRuns AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-job-executionproperty.html#cfn-glue-job-executionproperty-maxconcurrentruns
	MaxConcurrentRuns float64 `json:"MaxConcurrentRuns,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueJob_ExecutionProperty) AWSCloudFormationType() string {
	return "AWS::Glue::Job.ExecutionProperty"
}
