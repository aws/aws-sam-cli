package resources

import (
	"fmt"

	"github.com/awslabs/goformation/util"
)

// AWSCommonStringOrS3Location allows a field in a template (e.g. CodeUri) to be specified as
// either an S3 location object (Bucket, Key, Version), or a plain string.
type AWSCommonStringOrS3Location interface {
	String() string
}

type stringOrS3Location struct {
	location string
}

// String returns either the S3 bucket location (in s3://bucket/key#version format) or the string
func (sos3 *stringOrS3Location) String() string {
	return sos3.location
}

func (sos3 *stringOrS3Location) Scaffold(input Resource, propName string) (Resource, error) {

	value := input.Properties()[propName].Value()

	switch value.(type) {
	case string:
		sos3.location = util.ParsePrimitive(value).(string)

	case map[string]Property:

		s3l := &s3Location{}

		resource, err := s3l.Scaffold(input, propName)
		if err != nil {
			return nil, err
		}

		sos3.location = fmt.Sprintf("s3://%s/%s#%d", s3l.Bucket(), s3l.Key(), s3l.Version())

		return resource, nil

	}

	return nil, nil

}
