package cloudformation

// AWSGlueCrawler_Schedule AWS CloudFormation Resource (AWS::Glue::Crawler.Schedule)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-schedule.html
type AWSGlueCrawler_Schedule struct {

	// ScheduleExpression AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-glue-crawler-schedule.html#cfn-glue-crawler-schedule-scheduleexpression
	ScheduleExpression string `json:"ScheduleExpression,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSGlueCrawler_Schedule) AWSCloudFormationType() string {
	return "AWS::Glue::Crawler.Schedule"
}
