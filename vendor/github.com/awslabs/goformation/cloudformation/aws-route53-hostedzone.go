package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSRoute53HostedZone AWS CloudFormation Resource (AWS::Route53::HostedZone)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone.html
type AWSRoute53HostedZone struct {

	// HostedZoneConfig AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone.html#cfn-route53-hostedzone-hostedzoneconfig
	HostedZoneConfig *AWSRoute53HostedZone_HostedZoneConfig `json:"HostedZoneConfig,omitempty"`

	// HostedZoneTags AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone.html#cfn-route53-hostedzone-hostedzonetags
	HostedZoneTags []AWSRoute53HostedZone_HostedZoneTag `json:"HostedZoneTags,omitempty"`

	// Name AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone.html#cfn-route53-hostedzone-name
	Name string `json:"Name,omitempty"`

	// VPCs AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-route53-hostedzone.html#cfn-route53-hostedzone-vpcs
	VPCs []AWSRoute53HostedZone_VPC `json:"VPCs,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSRoute53HostedZone) AWSCloudFormationType() string {
	return "AWS::Route53::HostedZone"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSRoute53HostedZone) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSRoute53HostedZone) MarshalJSON() ([]byte, error) {
	type Properties AWSRoute53HostedZone
	return json.Marshal(&struct {
		Type       string
		Properties Properties
	}{
		Type:       r.AWSCloudFormationType(),
		Properties: (Properties)(*r),
	})
}

// UnmarshalJSON is a custom JSON unmarshalling hook that strips the outer
// AWS CloudFormation resource object, and just keeps the 'Properties' field.
func (r *AWSRoute53HostedZone) UnmarshalJSON(b []byte) error {
	type Properties AWSRoute53HostedZone
	res := &struct {
		Type       string
		Properties *Properties
	}{}
	if err := json.Unmarshal(b, &res); err != nil {
		fmt.Printf("ERROR: %s\n", err)
		return err
	}
	*r = AWSRoute53HostedZone(*res.Properties)
	return nil
}

// GetAllAWSRoute53HostedZoneResources retrieves all AWSRoute53HostedZone items from an AWS CloudFormation template
func (t *Template) GetAllAWSRoute53HostedZoneResources() map[string]AWSRoute53HostedZone {
	results := map[string]AWSRoute53HostedZone{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSRoute53HostedZone:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::Route53::HostedZone" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSRoute53HostedZone
						if err := json.Unmarshal(b, &result); err == nil {
							results[name] = result
						}
					}
				}
			}
		}
	}
	return results
}

// GetAWSRoute53HostedZoneWithName retrieves all AWSRoute53HostedZone items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSRoute53HostedZoneWithName(name string) (AWSRoute53HostedZone, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSRoute53HostedZone:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::Route53::HostedZone" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSRoute53HostedZone
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSRoute53HostedZone{}, errors.New("resource not found")
}
