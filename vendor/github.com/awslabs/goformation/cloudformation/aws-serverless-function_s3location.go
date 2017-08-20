package cloudformation

// AWSServerlessFunction_S3Location AWS CloudFormation Resource (AWS::Serverless::Function.S3Location)
// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#s3-location-object
type AWSServerlessFunction_S3Location struct {

	// Bucket AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
	Bucket string `json:"Bucket,omitempty"`

	// Key AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
	Key string `json:"Key,omitempty"`

	// Version AWS CloudFormation Property
	// Required: true
	// See: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
	Version int `json:"Version,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSServerlessFunction_S3Location) AWSCloudFormationType() string {
	return "AWS::Serverless::Function.S3Location"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSServerlessFunction_S3Location) AWSCloudFormationSpecificationVersion() string {
	return "2016-10-31"
}
