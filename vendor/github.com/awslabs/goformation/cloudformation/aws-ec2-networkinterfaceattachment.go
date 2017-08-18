package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSEC2NetworkInterfaceAttachment AWS CloudFormation Resource (AWS::EC2::NetworkInterfaceAttachment)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-network-interface-attachment.html
type AWSEC2NetworkInterfaceAttachment struct {

	// DeleteOnTermination AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-network-interface-attachment.html#cfn-ec2-network-interface-attachment-deleteonterm
	DeleteOnTermination bool `json:"DeleteOnTermination,omitempty"`

	// DeviceIndex AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-network-interface-attachment.html#cfn-ec2-network-interface-attachment-deviceindex
	DeviceIndex string `json:"DeviceIndex,omitempty"`

	// InstanceId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-network-interface-attachment.html#cfn-ec2-network-interface-attachment-instanceid
	InstanceId string `json:"InstanceId,omitempty"`

	// NetworkInterfaceId AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-network-interface-attachment.html#cfn-ec2-network-interface-attachment-networkinterfaceid
	NetworkInterfaceId string `json:"NetworkInterfaceId,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEC2NetworkInterfaceAttachment) AWSCloudFormationType() string {
	return "AWS::EC2::NetworkInterfaceAttachment"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSEC2NetworkInterfaceAttachment) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSEC2NetworkInterfaceAttachment) MarshalJSON() ([]byte, error) {
	type Properties AWSEC2NetworkInterfaceAttachment
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
func (r *AWSEC2NetworkInterfaceAttachment) UnmarshalJSON(b []byte) error {
	type Properties AWSEC2NetworkInterfaceAttachment
	res := &struct {
		Type       string
		Properties *Properties
	}{}
	if err := json.Unmarshal(b, &res); err != nil {
		fmt.Printf("ERROR: %s\n", err)
		return err
	}
	*r = AWSEC2NetworkInterfaceAttachment(*res.Properties)
	return nil
}

// GetAllAWSEC2NetworkInterfaceAttachmentResources retrieves all AWSEC2NetworkInterfaceAttachment items from an AWS CloudFormation template
func (t *Template) GetAllAWSEC2NetworkInterfaceAttachmentResources() map[string]AWSEC2NetworkInterfaceAttachment {
	results := map[string]AWSEC2NetworkInterfaceAttachment{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSEC2NetworkInterfaceAttachment:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::EC2::NetworkInterfaceAttachment" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSEC2NetworkInterfaceAttachment
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

// GetAWSEC2NetworkInterfaceAttachmentWithName retrieves all AWSEC2NetworkInterfaceAttachment items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSEC2NetworkInterfaceAttachmentWithName(name string) (AWSEC2NetworkInterfaceAttachment, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSEC2NetworkInterfaceAttachment:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::EC2::NetworkInterfaceAttachment" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSEC2NetworkInterfaceAttachment
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSEC2NetworkInterfaceAttachment{}, errors.New("resource not found")
}
