package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSAutoScalingScalingPolicy AWS CloudFormation Resource (AWS::AutoScaling::ScalingPolicy)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html
type AWSAutoScalingScalingPolicy struct {

	// AdjustmentType AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-adjustmenttype
	AdjustmentType string `json:"AdjustmentType,omitempty"`

	// AutoScalingGroupName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-autoscalinggroupname
	AutoScalingGroupName string `json:"AutoScalingGroupName,omitempty"`

	// Cooldown AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-cooldown
	Cooldown string `json:"Cooldown,omitempty"`

	// EstimatedInstanceWarmup AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-estimatedinstancewarmup
	EstimatedInstanceWarmup int `json:"EstimatedInstanceWarmup,omitempty"`

	// MetricAggregationType AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-metricaggregationtype
	MetricAggregationType string `json:"MetricAggregationType,omitempty"`

	// MinAdjustmentMagnitude AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-minadjustmentmagnitude
	MinAdjustmentMagnitude int `json:"MinAdjustmentMagnitude,omitempty"`

	// PolicyType AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-policytype
	PolicyType string `json:"PolicyType,omitempty"`

	// ScalingAdjustment AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-scalingadjustment
	ScalingAdjustment int `json:"ScalingAdjustment,omitempty"`

	// StepAdjustments AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-as-policy.html#cfn-as-scalingpolicy-stepadjustments
	StepAdjustments []AWSAutoScalingScalingPolicy_StepAdjustment `json:"StepAdjustments,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSAutoScalingScalingPolicy) AWSCloudFormationType() string {
	return "AWS::AutoScaling::ScalingPolicy"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSAutoScalingScalingPolicy) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSAutoScalingScalingPolicy) MarshalJSON() ([]byte, error) {
	type Properties AWSAutoScalingScalingPolicy
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
func (r *AWSAutoScalingScalingPolicy) UnmarshalJSON(b []byte) error {
	type Properties AWSAutoScalingScalingPolicy
	res := &struct {
		Type       string
		Properties *Properties
	}{}
	if err := json.Unmarshal(b, &res); err != nil {
		fmt.Printf("ERROR: %s\n", err)
		return err
	}
	*r = AWSAutoScalingScalingPolicy(*res.Properties)
	return nil
}

// GetAllAWSAutoScalingScalingPolicyResources retrieves all AWSAutoScalingScalingPolicy items from an AWS CloudFormation template
func (t *Template) GetAllAWSAutoScalingScalingPolicyResources() map[string]AWSAutoScalingScalingPolicy {
	results := map[string]AWSAutoScalingScalingPolicy{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSAutoScalingScalingPolicy:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::AutoScaling::ScalingPolicy" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSAutoScalingScalingPolicy
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

// GetAWSAutoScalingScalingPolicyWithName retrieves all AWSAutoScalingScalingPolicy items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSAutoScalingScalingPolicyWithName(name string) (AWSAutoScalingScalingPolicy, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSAutoScalingScalingPolicy:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::AutoScaling::ScalingPolicy" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSAutoScalingScalingPolicy
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSAutoScalingScalingPolicy{}, errors.New("resource not found")
}
