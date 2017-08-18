package cloudformation

import (
	"encoding/json"
	"errors"
	"fmt"
)

// AWSEFSFileSystem AWS CloudFormation Resource (AWS::EFS::FileSystem)
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html
type AWSEFSFileSystem struct {

	// FileSystemTags AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html#cfn-efs-filesystem-filesystemtags
	FileSystemTags []AWSEFSFileSystem_ElasticFileSystemTag `json:"FileSystemTags,omitempty"`

	// PerformanceMode AWS CloudFormation Property
	// Required: false
	// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html#cfn-efs-filesystem-performancemode
	PerformanceMode string `json:"PerformanceMode,omitempty"`
}

// AWSCloudFormationType returns the AWS CloudFormation resource type
func (r *AWSEFSFileSystem) AWSCloudFormationType() string {
	return "AWS::EFS::FileSystem"
}

// AWSCloudFormationSpecificationVersion returns the AWS Specification Version that this resource was generated from
func (r *AWSEFSFileSystem) AWSCloudFormationSpecificationVersion() string {
	return "1.4.2"
}

// MarshalJSON is a custom JSON marshalling hook that embeds this object into
// an AWS CloudFormation JSON resource's 'Properties' field and adds a 'Type'.
func (r *AWSEFSFileSystem) MarshalJSON() ([]byte, error) {
	type Properties AWSEFSFileSystem
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
func (r *AWSEFSFileSystem) UnmarshalJSON(b []byte) error {
	type Properties AWSEFSFileSystem
	res := &struct {
		Type       string
		Properties *Properties
	}{}
	if err := json.Unmarshal(b, &res); err != nil {
		fmt.Printf("ERROR: %s\n", err)
		return err
	}
	*r = AWSEFSFileSystem(*res.Properties)
	return nil
}

// GetAllAWSEFSFileSystemResources retrieves all AWSEFSFileSystem items from an AWS CloudFormation template
func (t *Template) GetAllAWSEFSFileSystemResources() map[string]AWSEFSFileSystem {
	results := map[string]AWSEFSFileSystem{}
	for name, untyped := range t.Resources {
		switch resource := untyped.(type) {
		case AWSEFSFileSystem:
			// We found a strongly typed resource of the correct type; use it
			results[name] = resource
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::EFS::FileSystem" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSEFSFileSystem
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

// GetAWSEFSFileSystemWithName retrieves all AWSEFSFileSystem items from an AWS CloudFormation template
// whose logical ID matches the provided name. Returns an error if not found.
func (t *Template) GetAWSEFSFileSystemWithName(name string) (AWSEFSFileSystem, error) {
	if untyped, ok := t.Resources[name]; ok {
		switch resource := untyped.(type) {
		case AWSEFSFileSystem:
			// We found a strongly typed resource of the correct type; use it
			return resource, nil
		case map[string]interface{}:
			// We found an untyped resource (likely from JSON) which *might* be
			// the correct type, but we need to check it's 'Type' field
			if resType, ok := resource["Type"]; ok {
				if resType == "AWS::EFS::FileSystem" {
					// The resource is correct, unmarshal it into the results
					if b, err := json.Marshal(resource); err == nil {
						var result AWSEFSFileSystem
						if err := json.Unmarshal(b, &result); err == nil {
							return result, nil
						}
					}
				}
			}
		}
	}
	return AWSEFSFileSystem{}, errors.New("resource not found")
}
