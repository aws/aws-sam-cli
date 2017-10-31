package cloudformation

// AWSGlueCrawler_Targets AWS CloudFormation Resource (AWS::Glue::Crawler.Targets)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-targets.html
type AWSGlueCrawler_Targets struct {

	// JdbcTargets AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-targets.html#cfn-glue-crawler-targets-jdbctargets
	JdbcTargets []AWSGlueCrawler_JdbcTarget `json:"JdbcTargets,omitempty"`

	// S3Targets AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-targets.html#cfn-glue-crawler-targets-s3targets
	S3Targets []AWSGlueCrawler_S3Target `json:"S3Targets,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueCrawler_Targets) AWSCloudFormationType() string {
	return "AWS::Glue::Crawler.Targets"
}
