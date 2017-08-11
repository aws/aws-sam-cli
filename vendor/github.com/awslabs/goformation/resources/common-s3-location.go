package resources

import (
	"net/url"
)

// TODO Document
type AWSCommonS3Location interface {
	Bucket() string
	Key() string
	Version() int
}

// S3Location represents an S3 location, ususally passed as the
// CodeUri for a Serverless Function
type s3Location struct {
	bucket  string
	key     string
	version int
}

func (s3 *s3Location) Bucket() string {
	return s3.bucket
}
func (s3 *s3Location) Key() string {
	return s3.key
}
func (s3 *s3Location) Version() int {
	return s3.version
}

func (s3 *s3Location) Scaffold(input Resource, propName string) (Resource, error) {

	propertyValue := input.Properties()[propName].Value()

	switch raw := propertyValue.(type) {
	case string:

		// The location has been specified as a string.
		// Parse out the bucket/key and populate an
		u, err := url.Parse(raw)
		if err != nil {
			return nil, err
		}

		s3.bucket = u.Host
		s3.key = u.Path

	case map[string]Property:

		for name, property := range raw {
			switch name {
			case "Bucket":
				if bucket, ok := property.Value().(string); ok {
					s3.bucket = bucket
				}
			case "Key":
				if key, ok := property.Value().(string); ok {
					s3.key = key
				}
			case "Version":
				if version, ok := property.Value().(int); ok {
					s3.version = version
				}
			}
		}

	}

	return nil, nil

}
