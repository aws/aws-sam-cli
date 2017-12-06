package cloudformation

// AWSGlueCrawler_S3Target AWS CloudFormation Resource (AWS::Glue::Crawler.S3Target)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-s3target.html
type AWSGlueCrawler_S3Target struct {

	// Exclusions AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-s3target.html#cfn-glue-crawler-s3target-exclusions
	Exclusions []string `json:"Exclusions,omitempty"`

	// Path AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-s3target.html#cfn-glue-crawler-s3target-path
	Path string `json:"Path,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueCrawler_S3Target) AWSCloudFormationType() string {
	return "AWS::Glue::Crawler.S3Target"
}
