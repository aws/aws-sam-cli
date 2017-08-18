package cloudformation

// AWSElasticLoadBalancingV2ListenerRule_RuleCondition AWS CloudFormation Resource (AWS::ElasticLoadBalancingV2::ListenerRule.RuleCondition)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-conditions.html
type AWSElasticLoadBalancingV2ListenerRule_RuleCondition struct {

	// Field AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-conditions.html#cfn-elasticloadbalancingv2-listenerrule-conditions-field
	Field string `json:"Field,omitempty"`

	// Values AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-conditions.html#cfn-elasticloadbalancingv2-listenerrule-conditions-values
	Values []string `json:"Values,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSElasticLoadBalancingV2ListenerRule_RuleCondition) AWSCloudFormationType() string {
	return "AWS::ElasticLoadBalancingV2::ListenerRule.RuleCondition"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSElasticLoadBalancingV2ListenerRule_RuleCondition) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
