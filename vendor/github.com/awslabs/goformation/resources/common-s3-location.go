package resources

import (
	"net/url"

	"github.com/awslabs/goformation/util"
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

		*s3 = s3Location{
			bucket: u.Host,
			key:    u.Path,
		}

	case map[interface{}]interface{}:

		location := &s3Location{}

		for key, value := range raw {
			switch key {
			case "Bucket":
				if v, ok := value.(string); ok {
					location.bucket = util.ParsePrimitive(v).(string)
				}
			case "Key":
				if v, ok := value.(string); ok {
					location.key = util.ParsePrimitive(v).(string)
				}
			case "Version":
				if v, ok := value.(int); ok {
					location.version = util.ParsePrimitive(v).(int)
				}
			}
		}

		s3 = location

	}

	return nil, nil

}
