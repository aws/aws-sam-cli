package cloudformation

// AWSApiGatewayMethod_Integration AWS CloudFormation Resource (AWS::ApiGateway::Method.Integration)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html
type AWSApiGatewayMethod_Integration struct {

	// CacheKeyParameters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-cachekeyparameters
	CacheKeyParameters []string `json:"CacheKeyParameters,omitempty"`

	// CacheNamespace AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-cachenamespace
	CacheNamespace string `json:"CacheNamespace,omitempty"`

	// Credentials AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-credentials
	Credentials string `json:"Credentials,omitempty"`

	// IntegrationHttpMethod AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-integrationhttpmethod
	IntegrationHttpMethod string `json:"IntegrationHttpMethod,omitempty"`

	// IntegrationResponses AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-integrationresponses
	IntegrationResponses []AWSApiGatewayMethod_IntegrationResponse `json:"IntegrationResponses,omitempty"`

	// PassthroughBehavior AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-passthroughbehavior
	PassthroughBehavior string `json:"PassthroughBehavior,omitempty"`

	// RequestParameters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-requestparameters
	RequestParameters map[string]string `json:"RequestParameters,omitempty"`

	// RequestTemplates AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-requesttemplates
	RequestTemplates map[string]string `json:"RequestTemplates,omitempty"`

	// Type AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-type
	Type string `json:"Type,omitempty"`

	// Uri AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-apitgateway-method-integration.html#cfn-apigateway-method-integration-uri
	Uri string `json:"Uri,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSApiGatewayMethod_Integration) AWSCloudFormationType() string {
	return "AWS::ApiGateway::Method.Integration"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSApiGatewayMethod_Integration) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
