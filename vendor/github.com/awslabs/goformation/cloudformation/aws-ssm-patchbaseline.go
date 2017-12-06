package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSSSMPatchBaseline AWS CloudFormation Resource (AWS::SSM::PatchBaseline)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html
type AWSSSMPatchBaseline struct {

	// ApprovalRules AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-approvalrules
	ApprovalRules *AWSSSMPatchBaseline_RuleGroup `json:"ApprovalRules,omitempty"`

	// ApprovedPatches AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-approvedpatches
	ApprovedPatches []string `json:"ApprovedPatches,omitempty"`

	// ApprovedPatchesComplianceLevel AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-approvedpatchescompliancelevel
	ApprovedPatchesComplianceLevel string `json:"ApprovedPatchesComplianceLevel,omitempty"`

	// Description AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-description
	Description string `json:"Description,omitempty"`

	// GlobalFilters AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-globalfilters
	GlobalFilters *AWSSSMPatchBaseline_PatchFilterGroup `json:"GlobalFilters,omitempty"`

	// Name AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-name
	Name string `json:"Name,omitempty"`

	// OperatingSystem AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-operatingsystem
	OperatingSystem string `json:"OperatingSystem,omitempty"`

	// PatchGroups AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-patchgroups
	PatchGroups []AWSSSMPatchBaseline_PatchGroup `json:"PatchGroups,omitempty"`

	// RejectedPatches AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-patchbaseline.html#cfn-ssm-patchbaseline-rejectedpatches
	RejectedPatches []string `json:"RejectedPatches,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSSSMPatchBaseline) AWSCloudFormationType() string {
	return "AWS::SSM::PatchBaseline"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSSSMPatchBaseline) MarshalJSON() ([]byte, error) {
	type Properties AWSSSMPatchBaseline
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
func (r *AWSSSMPatchBaseline) UnmarshalJSON(b []byte) error {
	type Properties AWSSSMPatchBaseline
	res := &struct {
		Type       string
		Properties *Properties
	}{}
	if err := json.Unmarshal(b, &res); err != nil {
		fmt.Printf("ERROR: %s\n", err)
		return err
	}

	// If the resource has no Properties set, it could be nil
	if res.Properties != nil {
		*r = AWSSSMPatchBaseline(*res.Properties)
	}

	return nil
}

// GetAllAWSSSMPatchBaselineResources retrieves all AWSSSMPatchBaseline items from an AWS CloudFormation template
func (t *Template) GetAllAWSSSMPatchBaselineResources() map[string]AWSSSMPatchBaseline {
	results := map[string]AWSSSMPatchBaseline{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSSSMPatchBaseline:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::SSM::PatchBaseline" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSSSMPatchBaseline
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

// GetAWSSSMPatchBaselineWithName retrieves all AWSSSMPatchBaseline items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSSSMPatchBaselineWithName(name string) (AWSSSMPatchBaseline, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSSSMPatchBaseline:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::SSM::PatchBaseline" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSSSMPatchBaseline
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSSSMPatchBaseline{}, errors.New("resource not found")
}
