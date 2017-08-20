package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSCloudTrailTrail AWS CloudFormation Resource (AWS::CloudTrail::Trail)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html
type AWSCloudTrailTrail struct {

	// CloudWatchLogsLogGroupArn AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-cloudwatchlogsloggroupaem
	CloudWatchLogsLogGroupArn string `json:"CloudWatchLogsLogGroupArn,omitempty"`

	// CloudWatchLogsRoleArn AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-cloudwatchlogsrolearn
	CloudWatchLogsRoleArn string `json:"CloudWatchLogsRoleArn,omitempty"`

	// EnableLogFileValidation AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-enablelogfilevalidation
	EnableLogFileValidation bool `json:"EnableLogFileValidation,omitempty"`

	// IncludeGlobalServiceEvents AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-includeglobalserviceevents
	IncludeGlobalServiceEvents bool `json:"IncludeGlobalServiceEvents,omitempty"`

	// IsLogging AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-islogging
	IsLogging bool `json:"IsLogging,omitempty"`

	// IsMultiRegionTrail AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-ismultiregiontrail
	IsMultiRegionTrail bool `json:"IsMultiRegionTrail,omitempty"`

	// KMSKeyId AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-kmskeyid
	KMSKeyId string `json:"KMSKeyId,omitempty"`

	// S3BucketName AWS CloudFormation Property
	// Required: true
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-s3bucketname
	S3BucketName string `json:"S3BucketName,omitempty"`

	// S3KeyPrefix AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-s3keyprefix
	S3KeyPrefix string `json:"S3KeyPrefix,omitempty"`

	// SnsTopicName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-snstopicname
	SnsTopicName string `json:"SnsTopicName,omitempty"`

	// Tags AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#cfn-cloudtrail-trail-tags
	Tags []Tag `json:"Tags,omitempty"`

	// TrailName AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudtrail-trail.html#aws-cloudtrail-trail-trailname
	TrailName string `json:"TrailName,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSCloudTrailTrail) AWSCloudFormationType() string {
	return "AWS::CloudTrail::Trail"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSCloudTrailTrail) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSCloudTrailTrail) MarshalJSON() ([]byte, error) {
	type Properties AWSCloudTrailTrail
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
func (r *AWSCloudTrailTrail) UnmarshalJSON(b []byte) error {
	type Properties AWSCloudTrailTrail
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
		*r = AWSCloudTrailTrail(*res.Properties)
	}

	return nil
}

// GetAllAWSCloudTrailTrailResources retrieves all AWSCloudTrailTrail items from an AWS CloudFormation template
func (t *Template) GetAllAWSCloudTrailTrailResources() map[string]AWSCloudTrailTrail {
	results := map[string]AWSCloudTrailTrail{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSCloudTrailTrail:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::CloudTrail::Trail" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSCloudTrailTrail
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

// GetAWSCloudTrailTrailWithName retrieves all AWSCloudTrailTrail items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSCloudTrailTrailWithName(name string) (AWSCloudTrailTrail, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSCloudTrailTrail:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::CloudTrail::Trail" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSCloudTrailTrail
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSCloudTrailTrail{}, errors.New("resource not found")
}
