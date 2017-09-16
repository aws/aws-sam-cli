package cloudformation

// AWSElasticLoadBalancingLoadBalancer_AppCookieStickinessPolicy AWS CloudFormation Resource (AWS::ElasticLoadBalancing::LoadBalancer.AppCookieStickinessPolicy)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-elb-AppCookieStickinessPolicy.html
type AWSElasticLoadBalancingLoadBalancer_AppCookieStickinessPolicy struct {

	// CookieName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-elb-AppCookieStickinessPolicy.html#cfn-elb-appcookiestickinesspolicy-cookiename
	CookieName string `json:"CookieName,omitempty"`

	// PolicyName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-elb-AppCookieStickinessPolicy.html#cfn-elb-appcookiestickinesspolicy-policyname
	PolicyName string `json:"PolicyName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSElasticLoadBalancingLoadBalancer_AppCookieStickinessPolicy) AWSCloudFormationType() string {
	return "AWS::ElasticLoadBalancing::LoadBalancer.AppCookieStickinessPolicy"
}
