package cloudformation

// AWSElasticBeanstalkApplicationVersion_SourceBundle AWS CloudFormation Resource (AWS::ElasticBeanstalk::ApplicationVersion.SourceBundle)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-sourcebundle.html
type AWSElasticBeanstalkApplicationVersion_SourceBundle struct {

	// S3Bucket AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-sourcebundle.html#cfn-beanstalk-sourcebundle-s3bucket
	S3Bucket string `json:"S3Bucket,omitempty"`

	// S3Key AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-beanstalk-sourcebundle.html#cfn-beanstalk-sourcebundle-s3key
	S3Key string `json:"S3Key,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSElasticBeanstalkApplicationVersion_SourceBundle) AWSCloudFormationType() string {
	return "AWS::ElasticBeanstalk::ApplicationVersion.SourceBundle"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSElasticBeanstalkApplicationVersion_SourceBundle) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
