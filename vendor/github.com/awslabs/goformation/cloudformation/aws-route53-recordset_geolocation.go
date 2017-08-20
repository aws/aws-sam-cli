package cloudformation

// AWSRoute53RecordSet_GeoLocation AWS CloudFormation Resource (AWS::Route53::RecordSet.GeoLocation)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset-geolocation.html
type AWSRoute53RecordSet_GeoLocation struct {

	// ContinentCode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset-geolocation.html#cfn-route53-recordset-geolocation-continentcode
	ContinentCode string `json:"ContinentCode,omitempty"`

	// CountryCode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset-geolocation.html#cfn-route53-recordset-geolocation-countrycode
	CountryCode string `json:"CountryCode,omitempty"`

	// SubdivisionCode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset-geolocation.html#cfn-route53-recordset-geolocation-subdivisioncode
	SubdivisionCode string `json:"SubdivisionCode,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSRoute53RecordSet_GeoLocation) AWSCloudFormationType() string {
	return "AWS::Route53::RecordSet.GeoLocation"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSRoute53RecordSet_GeoLocation) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}
